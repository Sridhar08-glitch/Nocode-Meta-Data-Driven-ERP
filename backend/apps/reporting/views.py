"""
Reporting REST API (PROJECT_HANDBOOK.md §25.3).

Workspace-scoped report CRUD + execution, snapshots, CSV/XLSX export and NQL
validation. Reads require an active membership; writes are role-gated. Execution
runs through NQL, so workspace isolation + field validation are enforced by the
query engine.
"""
import uuid

from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.nql.exceptions import NQLError

from .models import Dashboard, DashboardWidget, Report, ReportSnapshot
from .serializers import (
    DashboardSerializer,
    DashboardWidgetSerializer,
    ReportSerializer,
    ReportSnapshotListSerializer,
    ReportSnapshotSerializer,
)
from .services import DashboardService, ReportError, ReportService

_WRITE_ROLES = {"owner", "admin", "member"}


def _ws(request) -> uuid.UUID:
    ws = getattr(request, "workspace_id", None)
    if not ws:
        raise PermissionDenied("No active workspace. Send the X-Workspace-Slug header.")
    return ws if isinstance(ws, uuid.UUID) else uuid.UUID(str(ws))


def _member(request):
    m = getattr(request, "workspace_member", None)
    if m is None:
        raise PermissionDenied("No workspace membership for this request.")
    return m


def _require_write(request):
    m = _member(request)
    if getattr(m, "role", "") not in _WRITE_ROLES:
        raise PermissionDenied("Insufficient role for this action.")
    return m


def _get_report(request, pk) -> Report:
    r = Report.objects.filter(id=pk, workspace_id=_ws(request), deleted_at__isnull=True).first()
    if r is None:
        raise NotFound("Report not found")
    return r


def _execute(fn):
    try:
        return fn()
    except NQLError as exc:
        raise ValidationError(f"NQL error: {exc}") from exc
    except ReportError as exc:
        raise ValidationError(str(exc)) from exc


class ReportListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = Report.objects.filter(workspace_id=_ws(request), deleted_at__isnull=True)
        if request.query_params.get("report_type"):
            qs = qs.filter(report_type=request.query_params["report_type"])
        qs = qs.order_by("-created_at")
        return Response({"results": ReportSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = ReportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if Report.objects.filter(workspace_id=ws, slug=ser.validated_data["slug"]).exists():
            raise ValidationError("A report with this slug already exists")
        report = ser.save(workspace_id=ws)
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


class ReportDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        return Response(ReportSerializer(_get_report(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        report = _get_report(request, pk)
        ser = ReportSerializer(report, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ReportSerializer(report).data)

    def delete(self, request, pk):
        member = _require_write(request)
        _get_report(request, pk).soft_delete(member.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReportRunView(APIView):
    def post(self, request, pk):
        member = _member(request)
        report = _get_report(request, pk)
        if report.report_type == "pivot":
            data = _execute(lambda: ReportService.execute_pivot(
                report, _ws(request), member.user_id))
        else:
            data = _execute(lambda: ReportService.execute_report(
                report, _ws(request), member.user_id))
        return Response(data)


class ReportSnapshotView(APIView):
    def post(self, request, pk):
        member = _member(request)
        report = _get_report(request, pk)
        snap = _execute(lambda: ReportService.take_snapshot(
            report, _ws(request), member.user_id))
        return Response(ReportSnapshotSerializer(snap).data, status=status.HTTP_201_CREATED)


class ReportSnapshotListView(APIView):
    def get(self, request, pk):
        _member(request)
        _get_report(request, pk)
        qs = ReportSnapshot.objects.filter(
            report_id=pk, workspace_id=_ws(request)).order_by("-created_at")
        return Response({"results": ReportSnapshotListSerializer(qs, many=True).data,
                         "count": qs.count()})


class ReportSnapshotDetailView(APIView):
    def get(self, request, pk, snap_id):
        _member(request)
        _get_report(request, pk)
        snap = ReportSnapshot.objects.filter(
            id=snap_id, report_id=pk, workspace_id=_ws(request)).first()
        if snap is None:
            raise NotFound("Snapshot not found")
        return Response(ReportSnapshotSerializer(snap).data)


class ReportExportCsvView(APIView):
    def get(self, request, pk):
        member = _member(request)
        report = _get_report(request, pk)
        data = _execute(lambda: ReportService.export_to_csv(report, _ws(request), member.user_id))
        resp = HttpResponse(data, content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{report.slug}.csv"'
        return resp


class ReportExportXlsxView(APIView):
    def get(self, request, pk):
        member = _member(request)
        report = _get_report(request, pk)
        data = _execute(lambda: ReportService.export_to_xlsx(report, _ws(request), member.user_id))
        resp = HttpResponse(
            data,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp["Content-Disposition"] = f'attachment; filename="{report.slug}.xlsx"'
        return resp


class ReportExportPdfView(APIView):
    def get(self, request, pk):
        member = _member(request)
        report = _get_report(request, pk)
        data = _execute(lambda: ReportService.export_to_pdf(report, _ws(request), member.user_id))
        resp = HttpResponse(data, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{report.slug}.pdf"'
        return resp


class ValidateNqlView(APIView):
    def post(self, request):
        _member(request)
        errors = ReportService.validate_nql(
            nql_source=request.data.get("nql_source"),
            nql_ast=request.data.get("nql_ast"))
        return Response({"valid": not errors, "errors": errors})


# ── Dashboards (Phase 1.31) ───────────────────────────────────────────────────
def _get_dashboard(request, pk) -> Dashboard:
    d = Dashboard.objects.filter(
        id=pk, workspace_id=_ws(request), deleted_at__isnull=True).first()
    if d is None:
        raise NotFound("Dashboard not found")
    return d


class DashboardListCreateView(APIView):
    def get(self, request):
        _member(request)
        qs = Dashboard.objects.filter(
            workspace_id=_ws(request), deleted_at__isnull=True).order_by("-created_at")
        return Response({"results": DashboardSerializer(qs, many=True).data, "count": qs.count()})

    def post(self, request):
        _require_write(request)
        ser = DashboardSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ws = _ws(request)
        if Dashboard.objects.filter(workspace_id=ws, slug=ser.validated_data["slug"]).exists():
            raise ValidationError("A dashboard with this slug already exists")
        dash = ser.save(workspace_id=ws)
        return Response(DashboardSerializer(dash).data, status=status.HTTP_201_CREATED)


class DashboardDetailView(APIView):
    def get(self, request, pk):
        _member(request)
        return Response(DashboardSerializer(_get_dashboard(request, pk)).data)

    def patch(self, request, pk):
        _require_write(request)
        dash = _get_dashboard(request, pk)
        ser = DashboardSerializer(dash, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(DashboardSerializer(dash).data)

    def delete(self, request, pk):
        member = _require_write(request)
        _get_dashboard(request, pk).soft_delete(member.user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardWidgetListCreateView(APIView):
    def get(self, request, pk):
        _member(request)
        _get_dashboard(request, pk)
        qs = DashboardWidget.objects.filter(
            dashboard_id=pk, workspace_id=_ws(request)).order_by("grid_y", "grid_x")
        return Response(DashboardWidgetSerializer(qs, many=True).data)

    def post(self, request, pk):
        _require_write(request)
        _get_dashboard(request, pk)
        ser = DashboardWidgetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        widget = ser.save(workspace_id=_ws(request), dashboard_id=pk)
        return Response(DashboardWidgetSerializer(widget).data, status=status.HTTP_201_CREATED)


class DashboardWidgetDetailView(APIView):
    def _get(self, request, pk, wid):
        w = DashboardWidget.objects.filter(
            id=wid, dashboard_id=pk, workspace_id=_ws(request)).first()
        if w is None:
            raise NotFound("Widget not found")
        return w

    def patch(self, request, pk, wid):
        _require_write(request)
        _get_dashboard(request, pk)
        widget = self._get(request, pk, wid)
        ser = DashboardWidgetSerializer(widget, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(DashboardWidgetSerializer(widget).data)

    def delete(self, request, pk, wid):
        _require_write(request)
        _get_dashboard(request, pk)
        self._get(request, pk, wid).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardRunView(APIView):
    def post(self, request, pk):
        member = _member(request)
        dash = _get_dashboard(request, pk)
        data = _execute(lambda: DashboardService.run(
            dash, _ws(request), member.user_id, broadcast=True))
        return Response(data)


class DashboardExportPdfView(APIView):
    def get(self, request, pk):
        member = _member(request)
        dash = _get_dashboard(request, pk)
        data = _execute(lambda: DashboardService.export_to_pdf(dash, _ws(request), member.user_id))
        resp = HttpResponse(data, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{dash.slug}.pdf"'
        return resp
