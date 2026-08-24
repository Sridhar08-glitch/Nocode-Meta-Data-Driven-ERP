"""
Standard KPI seed set (Phase P2.13). Seeded per-workspace via the analytics ``/setup/`` endpoint
(KPIs are workspace-scoped). Idempotent (get_or_create by code). Each KPI is defined ONCE here and
reused by every scorecard/dashboard — no report defines KPIs independently.
"""
from __future__ import annotations


def _kpi(code, name, category, **kw):
    base = {"code": code, "name": name, "category": category, "source_type": "nql",
            "aggregate": "sum", "direction": "higher_better", "is_system": True}
    base.update(kw)
    return base


STANDARD_KPIS = [
    _kpi("revenue", "Revenue", "financial", nql_source="FROM sales_order",
         value_field="amount", aggregate="sum", unit="$"),
    _kpi("open_opportunities", "Open Opportunities", "crm", nql_source="FROM opportunity",
         aggregate="count"),
    _kpi("active_projects", "Active Projects", "projects", nql_source="FROM project",
         aggregate="count"),
    _kpi("headcount", "Headcount", "hr", nql_source="FROM employee", aggregate="count"),
    _kpi("open_tickets", "Open Tickets", "helpdesk", nql_source="FROM ticket",
         aggregate="count", direction="lower_better"),
    _kpi("csat", "CSAT", "helpdesk", nql_source="FROM ticket_csat", value_field="rating",
         aggregate="avg", target=4, warning_threshold=3, unit="/5"),
    _kpi("inventory_value", "Inventory Value", "inventory", source_type="native",
         native_key="inventory_value", unit="$"),
    _kpi("payroll_cost", "Payroll Cost", "payroll", source_type="native",
         native_key="payroll_cost", direction="lower_better", unit="$"),
    _kpi("manufacturing_output", "Manufacturing Output", "manufacturing", source_type="native",
         native_key="manufacturing_output", unit="units"),
]


def seed_standard_kpis(workspace_id, *, actor_id=None) -> int:
    from .models import KPIDefinition
    count = 0
    for spec in STANDARD_KPIS:
        _, created = KPIDefinition.objects.get_or_create(
            workspace_id=workspace_id, code=spec["code"],
            defaults={**{k: v for k, v in spec.items() if k != "code"},
                      "created_by": actor_id})
        count += 1 if created else 0
    return count
