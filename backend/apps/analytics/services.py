"""
Analytics / KPI services (Phase P2.13).

Evaluates KPIs (NQL aggregate via the reused ``apps.nql.execute_nql``, or a native evaluator),
applies thresholds → status, preserves snapshots, raises threshold alerts, and assembles role
scorecards. Reports/exports/dashboards/scheduling are REUSED from ``apps/reporting`` — this layer
adds only the KPI registry semantics. All reads are bulk (no per-row N+1).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.nql.services import execute_nql

from . import registry
from .models import KPIDefinition, KPISnapshot

# Role → KPI categories surfaced on that executive scorecard.
ROLE_SCORECARDS = {
    "ceo": ["financial", "crm", "projects", "manufacturing", "helpdesk", "operations"],
    "cfo": ["financial", "accounting", "payroll", "inventory", "assets"],
    "coo": ["manufacturing", "inventory", "procurement", "operations", "helpdesk"],
    "chro": ["hr", "payroll"],
    "cio": ["helpdesk", "projects", "assets"],
}


class AnalyticsError(Exception):  # noqa: N818 — domain error
    pass


def _d(v):
    try:
        return Decimal(str(v or 0))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def _emit(workspace_id, aggregate_id, event_type, payload, actor_id=None):
    from apps.eventstore.models import DomainEvent
    agg = uuid.UUID(str(aggregate_id))
    version = DomainEvent.objects.filter(
        aggregate_id=agg, aggregate_type="analytics_kpi").count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="analytics_kpi", aggregate_id=agg, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _status(value, kpi) -> str:
    target = _d(kpi.target)
    warn = _d(kpi.warning_threshold)
    if target == 0 and warn == 0:
        return "unknown"
    if kpi.direction == "lower_better":
        if value <= target:
            return "good"
        if warn and value <= warn:
            return "warning"
        return "critical"
    # higher_better
    if value >= target:
        return "good"
    if warn and value >= warn:
        return "warning"
    return "critical"


def _aggregate(rows, field, how) -> Decimal:
    if how == "count":
        return Decimal(len(rows))
    vals = [_d(r.get(field)) for r in rows if r.get(field) is not None]
    if not vals:
        return Decimal("0")
    if how == "sum":
        return sum(vals, Decimal("0"))
    if how == "avg":
        return (sum(vals, Decimal("0")) / Decimal(len(vals)))
    if how == "min":
        return min(vals)
    if how == "max":
        return max(vals)
    return sum(vals, Decimal("0"))


class KPIService:
    @staticmethod
    def evaluate(*, workspace_id, kpi, user_id=None) -> dict:
        """Compute a KPI's current value + status. NQL KPIs aggregate an entity query (reusing the
        NQL engine); native KPIs call a registered cross-module evaluator. Best-effort: a missing
        module/entity yields value 0 + status unknown (the KPI simply doesn't apply yet)."""
        value = Decimal("0")
        available = True
        try:
            if kpi.source_type == "native":
                fn = registry.get(kpi.native_key)
                value = _d(fn(workspace_id)) if fn else Decimal("0")
                available = fn is not None
            else:
                rows = execute_nql(workspace_id=workspace_id, source=kpi.nql_source,
                                   user_id=user_id)
                value = _aggregate(rows, kpi.value_field, kpi.aggregate)
        except Exception:  # noqa: BLE001 — entity/module not present in this workspace
            available = False
            value = Decimal("0")
        status = _status(value, kpi) if available else "unknown"
        variance = value - _d(kpi.target)
        return {"code": kpi.code, "name": kpi.name, "category": kpi.category,
                "value": str(value), "target": str(_d(kpi.target)), "status": status,
                "variance": str(variance), "unit": kpi.unit, "available": available}

    @staticmethod
    def evaluate_code(*, workspace_id, code, user_id=None) -> dict:
        kpi = KPIDefinition.objects.filter(workspace_id=workspace_id, code=code).first()
        if kpi is None:
            raise AnalyticsError("KPI not found.")
        result = KPIService.evaluate(workspace_id=workspace_id, kpi=kpi, user_id=user_id)
        _emit(workspace_id, kpi.id, "analytics.report.executed", {"code": code}, user_id)
        return result

    @staticmethod
    def evaluate_all(*, workspace_id, category=None, user_id=None) -> list[dict]:
        qs = KPIDefinition.objects.filter(workspace_id=workspace_id, is_active=True)
        if category:
            qs = qs.filter(category=category)
        return [KPIService.evaluate(workspace_id=workspace_id, kpi=k, user_id=user_id)
                for k in qs.order_by("category", "name")]

    @staticmethod
    def scorecard(*, workspace_id, role, user_id=None) -> dict:
        """A role-based executive scorecard (CEO/CFO/COO/CHRO/CIO) — KPIs grouped by category."""
        cats = ROLE_SCORECARDS.get(role.lower())
        qs = KPIDefinition.objects.filter(workspace_id=workspace_id, is_active=True)
        if cats is not None:
            qs = qs.filter(category__in=cats)
        results = [KPIService.evaluate(workspace_id=workspace_id, kpi=k, user_id=user_id)
                   for k in qs.order_by("category", "name")]
        return {"role": role, "kpis": results,
                "summary": {s: sum(1 for r in results if r["status"] == s)
                            for s in ("good", "warning", "critical", "unknown")}}

    @staticmethod
    def snapshot(*, workspace_id, period="", user_id=None) -> int:
        """Preserve current KPI values (reuses the snapshot concept). Module 27."""
        count = 0
        for kpi in KPIDefinition.objects.filter(workspace_id=workspace_id, is_active=True):
            r = KPIService.evaluate(workspace_id=workspace_id, kpi=kpi, user_id=user_id)
            KPISnapshot.objects.create(
                workspace_id=workspace_id, kpi_id=kpi.id, code=kpi.code,
                value=_d(r["value"]), target=_d(r["target"]), status=r["status"], period=period)
            count += 1
        _emit(workspace_id, uuid.UUID(int=0), "analytics.snapshot.created",
              {"count": count, "period": period}, user_id)
        return count

    @staticmethod
    def check_alerts(*, workspace_id, user_id=None) -> list[dict]:
        """Evaluate every KPI; emit ``analytics.alert.triggered`` for warning/critical breaches."""
        alerts = []
        for kpi in KPIDefinition.objects.filter(workspace_id=workspace_id, is_active=True):
            r = KPIService.evaluate(workspace_id=workspace_id, kpi=kpi, user_id=user_id)
            if r["status"] in ("warning", "critical"):
                _emit(workspace_id, kpi.id, "analytics.alert.triggered",
                      {"code": kpi.code, "status": r["status"], "value": r["value"]}, user_id)
                alerts.append(r)
        return alerts

    @staticmethod
    def trend(*, workspace_id, code, limit=12) -> list[dict]:
        snaps = KPISnapshot.objects.filter(
            workspace_id=workspace_id, code=code).order_by("-created_at")[:limit]
        return [{"value": str(s.value), "status": s.status, "period": s.period,
                 "at": s.created_at.isoformat()} for s in reversed(list(snaps))]
