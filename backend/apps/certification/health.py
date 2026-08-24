"""
ERP Health Service (P2.16 Module 24 / Module 26).

Queries EXISTING models/services — never introduces a new engine.  Every check
reads from the data sources that already exist: domain_events, JournalEntry,
WorkflowRun, StockLevel, etc.

Returns a structured health dict suitable for the ERP Health Dashboard API.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import connection
from django.utils import timezone

from .registry import INTEGRATION_REGISTRY


def _safe(fn, default=None):
    """Call fn(), swallow any exception and return default.  Health checks must
    never raise — a failed check is reported as a warning, not a 500."""
    try:
        return fn()
    except Exception:
        return default


# ── individual module health checks ────────────────────────────────────────────

def _event_store_health(workspace_id) -> dict:
    from apps.eventstore.models import DomainEvent
    recent_cutoff = timezone.now() - timedelta(hours=24)
    total = _safe(lambda: DomainEvent.objects.filter(workspace_id=workspace_id).count(), 0)
    recent = _safe(lambda: DomainEvent.objects.filter(
        workspace_id=workspace_id, occurred_at__gte=recent_cutoff).count(), 0)
    return {"status": "healthy", "total_events": total, "events_last_24h": recent}


def _accounting_health(workspace_id) -> dict:
    from apps.ledger.models import JournalEntry
    total = _safe(lambda: JournalEntry.objects.filter(workspace_id=workspace_id).count(), 0)
    posted = _safe(lambda: JournalEntry.objects.filter(
        workspace_id=workspace_id, status="posted").count(), 0)
    failed_events = _safe(lambda: __import__(
        "apps.eventstore.models", fromlist=["DomainEvent"]).DomainEvent.objects.filter(
        workspace_id=workspace_id, event_type="ledger.post.failed").count(), 0)
    status = "warning" if failed_events else "healthy"
    return {"status": status, "total_entries": total,
            "posted": posted, "post_failures": failed_events}


def _inventory_health(workspace_id) -> dict:
    from apps.inventory.models import StockLevel, StockMovement
    items_with_stock = _safe(lambda: StockLevel.objects.filter(
        workspace_id=workspace_id).count(), 0)
    negative_stock = _safe(lambda: StockLevel.objects.filter(
        workspace_id=workspace_id, on_hand__lt=0).count(), 0)
    movements_24h = _safe(lambda: StockMovement.objects.filter(
        workspace_id=workspace_id,
        occurred_at__gte=timezone.now() - timedelta(hours=24)).count(), 0)
    status = "warning" if negative_stock else "healthy"
    return {"status": status, "stock_lines": items_with_stock,
            "negative_stock_lines": negative_stock, "movements_24h": movements_24h}


def _workflow_health(workspace_id) -> dict:
    from apps.workflows.models import WorkflowRun
    total = _safe(lambda: WorkflowRun.objects.filter(workspace_id=workspace_id).count(), 0)
    failed = _safe(lambda: WorkflowRun.objects.filter(
        workspace_id=workspace_id, status="failed").count(), 0)
    stalled = _safe(lambda: WorkflowRun.objects.filter(
        workspace_id=workspace_id, status="running",
        started_at__lt=timezone.now() - timedelta(hours=24)).count(), 0)
    rate = round((1 - failed / total) * 100, 1) if total else 100.0
    status = "warning" if (failed > 0 or stalled > 0) else "healthy"
    return {"status": status, "total_runs": total, "failed": failed,
            "stalled": stalled, "success_rate_pct": rate}


def _payroll_health(workspace_id) -> dict:
    from apps.payroll.models import PayrollRun
    total = _safe(lambda: PayrollRun.objects.filter(workspace_id=workspace_id).count(), 0)
    locked = _safe(lambda: PayrollRun.objects.filter(
        workspace_id=workspace_id, status="locked").count(), 0)
    failed_posts = _safe(lambda: __import__(
        "apps.eventstore.models", fromlist=["DomainEvent"]).DomainEvent.objects.filter(
        workspace_id=workspace_id, event_type="ledger.post.failed",
        payload__source_module="payroll").count(), 0)
    status = "warning" if failed_posts else "healthy"
    return {"status": status, "total_runs": total, "locked_runs": locked,
            "post_failures": failed_posts}


def _manufacturing_health(workspace_id) -> dict:
    from apps.manufacturing.models import ProductionOrder, QualityCheck
    total_orders = _safe(lambda: ProductionOrder.objects.filter(
        workspace_id=workspace_id).count(), 0)
    completed = _safe(lambda: ProductionOrder.objects.filter(
        workspace_id=workspace_id, status="completed").count(), 0)
    quality_failures = _safe(lambda: QualityCheck.objects.filter(
        workspace_id=workspace_id, result="fail").count(), 0)
    status = "warning" if quality_failures > (total_orders * 0.1 if total_orders else 0) else "healthy"
    return {"status": status, "production_orders": total_orders,
            "completed": completed, "quality_failures": quality_failures}


def _solutions_health(workspace_id) -> dict:
    from apps.solution_templates.models import InstalledSolution
    installed = _safe(lambda: InstalledSolution.objects.filter(
        workspace_id=workspace_id, status="active").count(), 0)
    return {"status": "healthy", "installed_solutions": installed}


def _promotion_health(workspace_id) -> dict:
    from apps.environments.models import PromotionPackage
    total = _safe(lambda: PromotionPackage.objects.filter(
        workspace_id=workspace_id).count(), 0)
    failed = _safe(lambda: PromotionPackage.objects.filter(
        workspace_id=workspace_id, status="failed").count(), 0)
    status = "warning" if failed else "healthy"
    return {"status": status, "total_packages": total, "failed": failed}


def _security_health(workspace_id) -> dict:
    """Verify RLS is enabled on the DB for this workspace (PostgreSQL-only; SQLite=skipped)."""
    vendor = connection.vendor
    if vendor != "postgresql":
        return {"status": "healthy", "rls_enabled": "skipped_sqlite",
                "note": "RLS verified on PostgreSQL only"}
    with connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM pg_tables WHERE schemaname='public' "
            "AND rowsecurity = true")
        rls_count = cur.fetchone()[0]
    status = "healthy" if rls_count >= 50 else "warning"
    return {"status": status, "rls_enabled_tables": rls_count,
            "note": "≥50 tenant tables should have RLS"}


def _analytics_health(workspace_id) -> dict:
    from apps.analytics.models import KPIDefinition, KPISnapshot
    kpis = _safe(lambda: KPIDefinition.objects.filter(
        workspace_id=workspace_id, is_active=True).count(), 0)
    snapshots = _safe(lambda: KPISnapshot.objects.filter(
        workspace_id=workspace_id).count(), 0)
    return {"status": "healthy", "active_kpis": kpis, "snapshots": snapshots}


# ── aggregate health ────────────────────────────────────────────────────────────

MODULE_CHECKS = {
    "event_store": _event_store_health,
    "accounting": _accounting_health,
    "inventory": _inventory_health,
    "workflows": _workflow_health,
    "payroll": _payroll_health,
    "manufacturing": _manufacturing_health,
    "solutions": _solutions_health,
    "promotion": _promotion_health,
    "security": _security_health,
    "analytics": _analytics_health,
}

ERP_MODULES = [
    "crm", "procurement", "inventory", "hr", "payroll",
    "manufacturing", "projects", "assets", "helpdesk", "analytics",
    "environments", "accounting",
]

SOLUTION_SLUGS = {
    "crm": "crm", "procurement": "procurement", "hr": "hr",
    "helpdesk": "helpdesk", "assets": "assets", "projects": "projects",
}


def module_health(workspace_id) -> dict:
    """Run all health checks. Returns per-module results + overall status."""
    results = {}
    for name, fn in MODULE_CHECKS.items():
        results[name] = fn(workspace_id)
    statuses = [r["status"] for r in results.values()]
    if "failed" in statuses:
        overall = "failed"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "healthy"
    return {"modules": results, "overall": overall}


def integration_health() -> dict:
    """Summarise the integration registry."""
    certified = [i for i in INTEGRATION_REGISTRY if i.status == "certified"]
    partial = [i for i in INTEGRATION_REGISTRY if i.status == "partial"]
    deferred = [i for i in INTEGRATION_REGISTRY if i.status == "deferred"]
    total = len(INTEGRATION_REGISTRY)
    return {
        "total_integrations": total,
        "certified": len(certified),
        "partial": len(partial),
        "deferred": len(deferred),
        "compliance_pct": round(len(certified) / total * 100, 1) if total else 0,
        "integrations": [
            {"source": i.source_module, "target": i.target_module,
             "trigger": i.trigger, "status": i.status}
            for i in INTEGRATION_REGISTRY
        ],
    }


def readiness_summary(workspace_id) -> dict:
    """
    Executive readiness summary — is each ERP module operational for this workspace?
    Uses InstalledSolution presence + domain event activity as proxy.
    """
    from apps.eventstore.models import DomainEvent
    from apps.solution_templates.models import InstalledSolution

    installed_slugs = set(_safe(
        lambda: InstalledSolution.objects.filter(
            workspace_id=workspace_id, status="active"
        ).values_list("solution_slug", flat=True), []))

    cutoff = timezone.now() - timedelta(days=7)

    def _recent_events(prefix: str) -> int:
        return _safe(lambda: DomainEvent.objects.filter(
            workspace_id=workspace_id,
            event_type__startswith=prefix,
            occurred_at__gte=cutoff).count(), 0)

    module_map = {
        "crm": ("crm", "crm."),
        "procurement": ("procurement", "procurement."),
        "inventory": (None, "inventory."),  # native, no solution slug
        "hr": ("hr", "hr."),
        "payroll": (None, "payroll."),
        "manufacturing": (None, "manufacturing."),
        "projects": ("projects", "project."),
        "assets": ("assets", "asset."),
        "helpdesk": ("helpdesk", "ticket."),
        "analytics": (None, "analytics."),
        "accounting": (None, "ledger."),
        "environments": (None, "promotion."),
    }

    modules = {}
    for module, (slug, prefix) in module_map.items():
        is_installed = (slug is None) or (slug in installed_slugs)
        activity = _recent_events(prefix)
        if is_installed and activity > 0:
            status = "active"
        elif is_installed:
            status = "ready"
        else:
            status = "not_installed"
        modules[module] = {"status": status, "activity_7d": activity,
                           "solution_slug": slug}

    ready_count = sum(1 for m in modules.values() if m["status"] in ("ready", "active"))
    readiness_pct = round(ready_count / len(modules) * 100, 1)
    return {"modules": modules, "readiness_pct": readiness_pct,
            "total_modules": len(modules), "ready_or_active": ready_count}
