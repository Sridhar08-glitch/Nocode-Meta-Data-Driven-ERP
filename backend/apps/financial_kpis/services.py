"""
Financial KPI Library service (F13) — a thin facade over the frozen Analytics platform.

Owns ONLY: the catalog (AI-readiness descriptors) + provisioning. Evaluation, scorecards, snapshots,
alerts and trends are DELEGATED to `apps.analytics.KPIService` (no second KPI engine). Dashboards are
`apps.reporting` objects. F13 posts nothing to the GL.
"""
from __future__ import annotations

from .catalog import BY_CODE, CATALOG, CATEGORIES
from .provisioning import DASHBOARD_TEMPLATES, provision_financial_kpis


class FinancialKpiError(Exception):  # noqa: N818
    pass


class FinancialKpiCatalog:
    @staticmethod
    def describe(*, category=None) -> list[dict]:
        """The full library with AI-readiness metadata (name/formula/inputs/dependencies/…)."""
        items = CATALOG if category is None else [k for k in CATALOG if k.category == category]
        return [k.descriptor() for k in items]

    @staticmethod
    def describe_one(code) -> dict:
        k = BY_CODE.get(code)
        if k is None:
            raise FinancialKpiError(f"Unknown financial KPI '{code}'.")
        return k.descriptor()

    @staticmethod
    def categories() -> list[str]:
        return list(CATEGORIES)

    @staticmethod
    def dashboards() -> list[dict]:
        return [{"slug": slug, "name": name, "kpis": codes}
                for slug, (name, codes) in DASHBOARD_TEMPLATES.items()]

    @staticmethod
    def setup(*, workspace_id, actor_id=None) -> dict:
        return provision_financial_kpis(workspace_id, actor_id=actor_id)

    @staticmethod
    def evaluate(*, workspace_id, code, user_id=None) -> dict:
        """Delegate to the Analytics KPI engine (F13 never re-implements evaluation)."""
        from apps.analytics.services import KPIService
        return KPIService.evaluate_code(workspace_id=workspace_id, code=code, user_id=user_id)

    @staticmethod
    def evaluate_all(*, workspace_id, user_id=None) -> list[dict]:
        from apps.analytics.models import KPIDefinition
        from apps.analytics.services import KPIService
        codes = set(BY_CODE)
        out = []
        for kpi in KPIDefinition.objects.filter(
                workspace_id=workspace_id, category="financial", is_active=True):
            if kpi.code in codes:
                out.append(KPIService.evaluate(workspace_id=workspace_id, kpi=kpi, user_id=user_id))
        return out
