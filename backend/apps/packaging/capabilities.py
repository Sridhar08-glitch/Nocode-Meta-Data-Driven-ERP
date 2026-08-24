"""
Core capability + engine registry for the Solution Package Platform.

This is the authoritative declaration of (a) the platform's own semantic version, (b) the
single shared engines a package may require, and (c) the higher-level capabilities a package
may require. A capability/engine is reported *available* only if the code it points at can
actually be imported — so readiness is proven against the live source tree, not a static list.

Engines mirror ``apps.certification.report._ENGINE_LOCATIONS`` (the single-engine architecture
proof). ``apps/packaging/tests/test_capabilities.py`` asserts the two stay in sync so this
registry can never silently drift from the certified engine set.
"""
from __future__ import annotations

import importlib

# The platform's own version. Bump on every backward-incompatible core change so packages
# can pin ``min_core_version`` / ``max_core_version`` against it.
CORE_VERSION = "2.0.0"

# Engine name → dotpath of its single canonical implementation.
ENGINES: dict[str, str] = {
    "accounting": "apps.ledger.services.GLBus",
    "inventory": "apps.inventory.services.InventoryService",
    "workflow": "apps.workflows.services.WorkflowService",
    "analytics": "apps.analytics.services.KPIService",
    "notification": "apps.notifications.services.NotificationService",
    "audit": "apps.eventstore.events.DomainEventFactory",
    "dependency": "apps.metadata.impact",
    "promotion": "apps.environments.services.PromotionService",
    "config_vcs": "apps.config_vcs.services",
    "event_store": "apps.eventstore.models.DomainEvent",
    "numbering": "apps.numbering.services.NumberingService",
    "nql": "apps.nql.compiler.NQLCompiler",
    "reporting": "apps.reporting.services.ReportService",
    "rls": "apps.tenancy.rls",
    "rbac": "apps.permissions.services",
}

# Higher-level capability name → dotpath proving it exists. A capability is a feature a package
# composes against (richer than a raw engine). Each points at a module/attr that must import.
CAPABILITIES: dict[str, str] = {
    # metadata / no-code core
    "metadata": "apps.metadata.models.EntityDefinition",
    "dynamic_entities": "apps.physical_tables.services.PhysicalTableGenerator",
    "schema_registry": "apps.schema_registry.services.SchemaRegistryService",
    "dynamic_forms": "apps.metadata.services.FormSchemaService",
    "views": "apps.metadata.models.ViewDefinition",
    "relationships": "apps.relationships.services",
    "computed_fields": "apps.computed.services.safe_eval",
    "business_rules": "apps.rules.models.BusinessRule",
    # access
    "rbac": "apps.permissions.services",
    "abac": "apps.permissions.services",
    "field_masking": "apps.permissions.models.DataMaskingRule",
    "multi_tenancy": "apps.tenancy.models.Workspace",
    "row_level_security": "apps.tenancy.rls",
    # automation / messaging
    "workflows": "apps.workflows.services.WorkflowService",
    "notifications": "apps.notifications.services.NotificationService",
    "approvals": "apps.approvals.services",
    "sla": "apps.sla.services",
    "realtime": "apps.realtime.broadcast",
    # data / analytics
    "reports": "apps.reporting.services.ReportService",
    "dashboards": "apps.reporting.models.Dashboard",
    "analytics_kpi": "apps.analytics.services.KPIService",
    "search": "apps.search.services",
    "import_export": "apps.staging.services",
    "documents": "apps.documents.services",
    # finance / ops engines
    "accounting": "apps.ledger.services.GLBus",
    "inventory": "apps.inventory.services.InventoryService",
    "numbering": "apps.numbering.services.NumberingService",
    # Financial Platform sub-engines (reusable by every package; never re-implemented in a package).
    "credit_engine": "apps.credits.services.CreditService",
    "collections_engine": "apps.collections_engine.services.CollectionsService",
    "tax_engine": "apps.taxes.services.TaxService",
    "revenue_recognition": "apps.revenue.services.RevenueService",
    "financial_statements": "apps.financial_reports.services.StatementService",
    "settlement_engine": "apps.settlement.services.SettlementService",
    "multi_currency": "apps.currency.services.CurrencyService",
    "fx_revaluation": "apps.currency.fx.FxService",
    "cash_management": "apps.cash.services.CashService",
    "bank_reconciliation": "apps.cash.services.ReconciliationService",
    "financial_dimensions": "apps.dimensions.services.DimensionService",
    "budgeting": "apps.budgets.services.BudgetService",
    "forecasting": "apps.budgets.services.BudgetService",
    # Multi-company / consolidation (F11) — Company is a shared PLATFORM object.
    "companies": "apps.companies.services.CompanyService",
    "consolidation": "apps.consolidation.services.ConsolidationService",
    "intercompany": "apps.consolidation.services.IntercompanyService",
    # Treasury (F12) — borrowings/investments, interest, liquidity, debt schedules.
    "treasury": "apps.treasury.services.TreasuryService",
    "treasury_schedules": "apps.treasury.services.ScheduleService",
    "liquidity": "apps.treasury.services.LiquidityService",
    # Financial KPI Library (F13) — native finance KPI catalog over the frozen analytics engine.
    "financial_kpi_library": "apps.financial_kpis.services.FinancialKpiCatalog",
    # System-Entity Adapter (B0) — render native-model engines through the Generic Runtime.
    "system_entity_adapter": "apps.system_entities.services.SystemEntityService",
    # platform / governance
    "event_store": "apps.eventstore.models.DomainEvent",
    "audit": "apps.audit.models.AuditLog",
    "config_versioning": "apps.config_vcs.services",
    "dependency_analysis": "apps.metadata.impact",
    "environment_promotion": "apps.environments.services.PromotionService",
    "studio_navigation": "apps.studio.models.Navigation",
    "branding": "apps.branding.services",
    "localization": "apps.localization.services",
    "feature_flags": "apps.feature_flags.services",
    "solution_packages": "apps.solution_templates.services",
    # Guard Framework (Platform Gap A) — declarative cross-record validation.
    "cross_record_validation": "apps.guards.services.GuardService",
    # Aggregation Framework (Platform Gap CG-2) — cross-record aggregation + calculation + persist.
    "cross_record_aggregation": "apps.aggregation.services.AggregationService",
}


def _importable(dotpath: str) -> bool:
    """True if ``dotpath`` resolves to a real module or module attribute."""
    try:
        importlib.import_module(dotpath)
        return True
    except ImportError:
        pass
    if "." not in dotpath:
        return False
    module_path, attr = dotpath.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return False
    return hasattr(module, attr)


def engine_available(name: str) -> bool:
    dotpath = ENGINES.get(name)
    return bool(dotpath) and _importable(dotpath)


def capability_available(name: str) -> bool:
    dotpath = CAPABILITIES.get(name)
    return bool(dotpath) and _importable(dotpath)


def list_engines() -> dict:
    return {name: {"location": dot, "available": _importable(dot)}
            for name, dot in ENGINES.items()}


def list_capabilities() -> dict:
    return {name: {"location": dot, "available": _importable(dot)}
            for name, dot in CAPABILITIES.items()}


def missing_engines(names) -> list[str]:
    return [n for n in (names or []) if not engine_available(n)]


def missing_capabilities(names) -> list[str]:
    return [n for n in (names or []) if not capability_available(n)]


def unknown_engines(names) -> list[str]:
    return [n for n in (names or []) if n not in ENGINES]


def unknown_capabilities(names) -> list[str]:
    return [n for n in (names or []) if n not in CAPABILITIES]
