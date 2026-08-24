"""
ReportService (PROJECT_HANDBOOK.md §25.1).

Reports are saved NQL queries. Execution compiles ``report.nql_ast`` through the
NQL engine (never raw SQL), caps results at ``NEXUS_NQL_MAX_LIMIT``, applies
``display_config`` (column ordering + label overrides), and can pivot, snapshot,
or export to CSV/XLSX. Pivot aggregation is done in Python — never a raw user
``GROUP BY``.
"""
from __future__ import annotations

import csv
import io

from django.conf import settings

from apps.nql.services import execute_nql

from .models import Dashboard, DashboardWidget, Report, ReportSnapshot

MAX_ROWS = getattr(settings, "NEXUS_NQL_MAX_LIMIT", 10000)
SNAPSHOTS_KEPT = 5


def workspace_watermark(workspace_id) -> str:
    """Best-effort white-label watermark text from workspace branding (app name)."""
    try:
        from apps.branding.models import WorkspaceBranding
        b = WorkspaceBranding.objects.filter(workspace_id=workspace_id).first()
        return (b.app_name if b and b.app_name else "") or ""
    except Exception:  # noqa: BLE001 — branding is optional; never block a PDF
        return ""

_AGGS = {
    "sum": lambda vals: sum(_nums(vals)),
    "avg": lambda vals: (sum(_nums(vals)) / len(_nums(vals))) if _nums(vals) else 0,
    "count": lambda vals: len(vals),
    "min": lambda vals: min(_nums(vals)) if _nums(vals) else None,
    "max": lambda vals: max(_nums(vals)) if _nums(vals) else None,
}


class ReportError(Exception):  # noqa: N818 — domain error
    pass


def _nums(values):
    out = []
    for v in values:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _columns(display_config: dict, rows: list[dict]) -> list[dict]:
    """Resolve output columns from display_config or the first row's keys."""
    cfg_cols = (display_config or {}).get("columns")
    labels = (display_config or {}).get("labels", {})
    if cfg_cols:
        out = []
        for c in cfg_cols:
            if isinstance(c, dict):
                key = c.get("key")
                out.append({"key": key, "label": c.get("label") or labels.get(key) or key})
            else:
                out.append({"key": c, "label": labels.get(c, c)})
        return out
    keys = list(rows[0].keys()) if rows else []
    return [{"key": k, "label": labels.get(k, k)} for k in keys]


class ReportService:
    @staticmethod
    def execute_report(report, workspace_id, requesting_user_id=None, params=None) -> dict:
        rows = execute_nql(workspace_id=workspace_id, source=report.nql_ast,
                           user_id=requesting_user_id)
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        columns = _columns(report.display_config, rows)
        return {"columns": columns, "rows": rows, "total_count": len(rows),
                "truncated": truncated}

    @staticmethod
    def execute_pivot(report, workspace_id, requesting_user_id=None) -> dict:
        cfg = report.display_config or {}
        row_field = cfg.get("row_field")
        col_field = cfg.get("column_field")
        value_field = cfg.get("value_field")
        agg = (cfg.get("agg") or "count").lower()
        if not row_field or agg not in _AGGS:
            raise ReportError("pivot requires display_config.row_field and a valid agg")
        rows = execute_nql(workspace_id=workspace_id, source=report.nql_ast,
                           user_id=requesting_user_id)[:MAX_ROWS]
        row_keys, col_keys = [], []
        buckets: dict = {}
        for r in rows:
            rk = r.get(row_field)
            ck = r.get(col_field) if col_field else "_total"
            if rk not in row_keys:
                row_keys.append(rk)
            if ck not in col_keys:
                col_keys.append(ck)
            buckets.setdefault((rk, ck), []).append(
                r.get(value_field) if value_field else 1)
        matrix = []
        for rk in row_keys:
            line = []
            for ck in col_keys:
                vals = buckets.get((rk, ck), [])
                line.append(_AGGS[agg](vals) if vals else None)
            matrix.append(line)
        return {"row_field": row_field, "column_field": col_field, "agg": agg,
                "row_values": row_keys, "column_values": col_keys, "matrix": matrix}

    @staticmethod
    def take_snapshot(report, workspace_id, generated_by=None, duration_ms=0) -> ReportSnapshot:
        result = ReportService.execute_report(report, workspace_id, generated_by)
        snap = ReportSnapshot.objects.create(
            report_id=report.id, workspace_id=workspace_id,
            row_count=result["total_count"], data=result["rows"],
            generated_by=generated_by, duration_ms=duration_ms)
        # prune: keep the most recent SNAPSHOTS_KEPT per report
        stale = (ReportSnapshot.objects
                 .filter(report_id=report.id, workspace_id=workspace_id)
                 .order_by("-created_at")
                 .values_list("id", flat=True)[SNAPSHOTS_KEPT:])
        if stale:
            ReportSnapshot.objects.filter(id__in=list(stale)).delete()
        return snap

    @staticmethod
    def export_to_csv(report, workspace_id, requesting_user_id=None) -> bytes:
        result = ReportService.execute_report(report, workspace_id, requesting_user_id)
        buf = io.StringIO()
        writer = csv.writer(buf)
        keys = [c["key"] for c in result["columns"]]
        writer.writerow([c["label"] for c in result["columns"]])
        for row in result["rows"]:
            writer.writerow([row.get(k, "") for k in keys])
        return buf.getvalue().encode("utf-8")

    @staticmethod
    def export_to_xlsx(report, workspace_id, requesting_user_id=None) -> bytes:
        from openpyxl import Workbook
        result = ReportService.execute_report(report, workspace_id, requesting_user_id)
        wb = Workbook()
        ws = wb.active
        ws.title = (report.name or "Report")[:31]
        keys = [c["key"] for c in result["columns"]]
        ws.append([c["label"] for c in result["columns"]])
        for row in result["rows"]:
            ws.append([row.get(k, "") for k in keys])
        widths = (report.display_config or {}).get("column_widths", {})
        for idx, key in enumerate(keys, start=1):
            if key in widths:
                ws.column_dimensions[chr(64 + idx)].width = widths[key]
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    @staticmethod
    def export_to_pdf(report, workspace_id, requesting_user_id=None) -> bytes:
        from .pdf import render_pdf
        result = ReportService.execute_report(report, workspace_id, requesting_user_id)
        document = {
            "title": report.name or "Report",
            "subtitle": report.description or "",
            "watermark": workspace_watermark(workspace_id),
            "tables": [{"title": "", "columns": result["columns"], "rows": result["rows"]}],
        }
        return render_pdf(document)

    @staticmethod
    def validate_nql(*, nql_source=None, nql_ast=None) -> list[str]:
        """Return a list of validation errors (empty = valid)."""
        from apps.nql.exceptions import NQLError
        from apps.nql.parser import parse_nql_text
        errors: list[str] = []
        try:
            if nql_source:
                parse_nql_text(nql_source)
            elif nql_ast is not None:
                from apps.nql.ast import query_from_json
                query_from_json(nql_ast)
            else:
                errors.append("Provide nql_source or nql_ast")
        except NQLError as exc:
            errors.append(str(exc))
        except Exception as exc:  # noqa: BLE001 — surface any parse problem as a validation error
            errors.append(str(exc))
        return errors


class DashboardError(Exception):  # noqa: N818 — domain error
    pass


class DashboardService:
    """Dashboards = a collection of widgets; ``run`` resolves each widget's data
    (report widgets execute their NQL through ReportService; static widgets return
    their config). Live widget refreshes can be pushed via realtime.broadcast_dashboard."""

    @staticmethod
    def get_dashboard(workspace_id, dashboard_id) -> Dashboard:
        d = Dashboard.objects.filter(
            id=dashboard_id, workspace_id=workspace_id, deleted_at__isnull=True).first()
        if d is None:
            raise DashboardError("Dashboard not found")
        return d

    @staticmethod
    def _run_widget(widget: DashboardWidget, workspace_id, user_id) -> dict:
        base = {"widget_id": str(widget.id), "widget_type": widget.widget_type,
                "title": widget.title}
        if widget.widget_type in ("report", "metric_card") and widget.report_id:
            report = Report.objects.filter(
                id=widget.report_id, workspace_id=workspace_id,
                deleted_at__isnull=True).first()
            if report is None:
                return {**base, "error": "report not found"}
            try:
                cfg = report.display_config or {}
                # A pivot widget needs a row_field + valid agg; if the report wasn't
                # configured for pivoting, degrade gracefully to a table render instead
                # of surfacing a "pivot requires…" error on the dashboard.
                if report.report_type == "pivot" and cfg.get("row_field") and (cfg.get("agg", "count") or "count").lower() in _AGGS:
                    base["result"] = ReportService.execute_pivot(report, workspace_id, user_id)
                else:
                    base["result"] = ReportService.execute_report(report, workspace_id, user_id)
            except Exception as exc:  # noqa: BLE001 — one bad widget shouldn't sink the dashboard
                base["error"] = str(exc)
            return base
        # static widgets (text / iframe / quick_links / activity_feed) → echo config
        base["config"] = widget.config or {}
        return base

    @staticmethod
    def run(dashboard: Dashboard, workspace_id, user_id=None, *, broadcast=False) -> dict:
        widgets = DashboardWidget.objects.filter(
            dashboard_id=dashboard.id, workspace_id=workspace_id).order_by("grid_y", "grid_x")
        results = [DashboardService._run_widget(w, workspace_id, user_id) for w in widgets]
        out = {"dashboard_id": str(dashboard.id), "name": dashboard.name, "widgets": results}
        if broadcast:
            try:
                from apps.realtime.broadcast import broadcast_dashboard
                broadcast_dashboard(workspace_id=workspace_id, dashboard_id=dashboard.id,
                                    payload={"widget_count": len(results)})
            except Exception:  # noqa: BLE001 — realtime push is best-effort
                pass
        return out

    @staticmethod
    def export_to_pdf(dashboard: Dashboard, workspace_id, user_id=None) -> bytes:
        from .pdf import render_pdf
        run = DashboardService.run(dashboard, workspace_id, user_id)
        tables, metrics = [], []
        for w in run["widgets"]:
            res = w.get("result")
            if res and "columns" in res:  # tabular report widget
                tables.append({"title": w.get("title") or "", "columns": res["columns"],
                               "rows": res["rows"]})
            elif res and "matrix" in res:  # pivot — flatten to a single metric line
                metrics.append({"label": w.get("title") or "Pivot",
                                "value": f"{len(res['row_values'])}×{len(res['column_values'])}"})
        return render_pdf({
            "title": dashboard.name or "Dashboard",
            "subtitle": dashboard.description or "",
            "watermark": workspace_watermark(workspace_id),
            "metrics": metrics, "tables": tables,
        })
