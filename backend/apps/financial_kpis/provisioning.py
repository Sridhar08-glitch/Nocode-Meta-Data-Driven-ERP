"""
Financial KPI provisioning (F13) — seed the standard finance KPI DEFINITIONS + dashboard TEMPLATES
into a workspace, idempotently, by REUSING `analytics.KPIDefinition` and `reporting.Dashboard`/
`DashboardWidget` (§2/§5: no new KPI or dashboard engine — templates are seeds users clone via the
existing Dashboard Builder). Each KPI is a `native` KPIDefinition whose `native_key` resolves to the
F13 evaluator; `category="financial"` so it integrates with the existing CFO/CEO scorecards.
"""
from __future__ import annotations

from .catalog import CATALOG

# Standard finance dashboards (seeds). Each = slug → (name, [kpi codes as metric-card widgets]).
DASHBOARD_TEMPLATES = {
    "cfo-overview": ("CFO Overview", [
        "gl_total_revenue", "net_profit_margin_pct", "working_capital", "current_ratio",
        "debt_to_equity", "return_on_equity_pct", "net_liquidity", "cash_runway_months"]),
    "controller-operations": ("Controller — Operations", [
        "dso_days", "dpo_days", "dio_days", "cash_conversion_cycle", "ar_overdue_pct",
        "gross_margin_pct", "opex_ratio_pct", "budget_variance_pct"]),
    "treasury-dashboard": ("Treasury Dashboard", [
        "net_liquidity", "cash_balance", "total_borrowings", "total_investments",
        "interest_coverage", "fx_net_impact"]),
    "executive-financial": ("Executive — Financial", [
        "gl_total_revenue", "revenue_growth_pct", "net_profit_margin_pct", "return_on_assets_pct",
        "current_ratio", "net_liquidity"]),
}


def _seed_kpis(workspace_id, actor_id=None) -> int:
    from apps.analytics.models import KPIDefinition
    created = 0
    for k in CATALOG:
        _, was_created = KPIDefinition.objects.get_or_create(
            workspace_id=workspace_id, code=k.code,
            defaults={
                "name": k.name, "description": k.explanation, "category": "financial",
                "source_type": "native", "native_key": k.native_key,
                "target": k.target, "warning_threshold": k.warning, "direction": k.direction,
                "unit": k.unit, "owner": "financial_kpis", "is_system": True, "created_by": actor_id})
        created += 1 if was_created else 0
    return created


def _seed_dashboards(workspace_id, actor_id=None) -> int:
    from apps.reporting.models import Dashboard, DashboardWidget
    created = 0
    for slug, (name, codes) in DASHBOARD_TEMPLATES.items():
        dash, was_created = Dashboard.objects.get_or_create(
            workspace_id=workspace_id, slug=slug,
            defaults={"name": name, "description": f"Standard finance template — {name}.",
                      "is_public": True, "created_by": actor_id})
        if not was_created:
            continue                                   # leave existing (possibly customized) alone
        created += 1
        for i, code in enumerate(codes):
            DashboardWidget.objects.create(
                workspace_id=workspace_id, dashboard_id=dash.id, widget_type="metric_card",
                title="", config={"kpi_code": code}, grid_x=(i % 4) * 3, grid_y=(i // 4) * 4,
                grid_w=3, grid_h=4)
    return created


def provision_financial_kpis(workspace_id, *, actor_id=None) -> dict:
    """Idempotently seed the finance KPI library + dashboard templates for a workspace."""
    kpis = _seed_kpis(workspace_id, actor_id)
    dashboards = _seed_dashboards(workspace_id, actor_id)
    return {"kpis_created": kpis, "kpis_total": len(CATALOG),
            "dashboards_created": dashboards, "dashboards_total": len(DASHBOARD_TEMPLATES)}
