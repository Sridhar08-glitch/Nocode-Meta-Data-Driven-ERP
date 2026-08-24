"""Sridhar ERP root URLconf."""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    # Operational probes (liveness/readiness) — unauthenticated, NOT tenant-scoped.
    path("", include("apps.ops.urls")),
    # Auth
    path("api/v1/auth/", include("apps.accounts.urls")),
    # Tenancy / workspaces
    path("api/v1/workspaces/", include("apps.tenancy.urls")),
    # Metadata (entity & field definitions) — public CRUD API
    path("api/v1/metadata/", include("apps.metadata.urls")),
    # Auto-generated CRUD over dynamic entities (NQL-backed, RBAC/ABAC-enforced)
    path("api/v1/data/", include("apps.records.urls")),
    # Relationships
    path("api/v1/relationships/", include("apps.relationships.urls")),
    # NQL query endpoint
    path("api/v1/nql/", include("apps.nql.urls")),
    # Permissions
    path("api/v1/permissions/", include("apps.permissions.urls")),
    # Workflows
    path("api/v1/workflows/", include("apps.workflows.urls")),
    # Reporting & dashboards
    path("api/v1/reports/", include("apps.reporting.urls")),
    # Search
    path("api/v1/search/", include("apps.search.urls")),
    # Documents
    path("api/v1/documents/", include("apps.documents.urls")),
    # Notifications
    path("api/v1/notifications/", include("apps.notifications.urls")),
    # Audit
    path("api/v1/audit/", include("apps.audit.urls")),
    # Activity feed
    path("api/v1/activity/", include("apps.activity.urls")),
    # Backups
    path("api/v1/backups/", include("apps.backups.urls")),
    # Config VCS
    path("api/v1/config-vcs/", include("apps.config_vcs.urls")),
    # Feature flags
    path("api/v1/feature-flags/", include("apps.feature_flags.urls")),
    # User personalization & appearance (Phase P0) — per-user prefs over the branding pipeline
    path("api/v1/me/", include("apps.personalization.urls")),
    # Dashboards (Phase 1.31)
    path("api/v1/dashboards/", include("apps.reporting.urls_dashboards")),
    # Studio: applications / home layouts / navigation (Phase 1.32)
    path("api/v1/applications/", include("apps.studio.urls_applications")),
    path("api/v1/home-layouts/", include("apps.studio.urls_home")),
    path("api/v1/navigation/", include("apps.studio.urls_navigation")),
    # Template backends: email + document/PDF (Phase 1.33)
    path("api/v1/templates/email/", include("apps.email_templates.urls")),
    path("api/v1/templates/documents/", include("apps.document_templates.urls")),
    # Business process catalog (Phase 1.34)
    path("api/v1/process-catalog/", include("apps.process_catalog.urls")),
    # Numbering engine (Phase P2.1) — gapless document number sequences
    path("api/v1/numbering/", include("apps.numbering.urls")),
    # General Ledger / posting bus (Phase P2.2)
    path("api/v1/ledger/", include("apps.ledger.urls")),
    # Inventory engine (Phase P2.4)
    path("api/v1/inventory/", include("apps.inventory.urls")),
    # Solution Template Framework (Phase P2.4A)
    path("api/v1/solution-templates/", include("apps.solution_templates.urls")),
    # Procurement solution — native integrity seams (Phase P2.5)
    path("api/v1/procurement/", include("apps.procurement.urls")),
    # CRM solution — thin lifecycle seams (Phase P2.6)
    path("api/v1/crm/", include("apps.crm.urls")),
    # HR solution — thin lifecycle seams (Phase P2.7)
    path("api/v1/hr/", include("apps.hr.urls")),
    # Payroll Engine — native (Phase P2.8)
    path("api/v1/payroll/", include("apps.payroll.urls")),
    # Asset Management — hybrid native/framework (Phase P2.9)
    path("api/v1/assets/", include("apps.assets.urls")),
    # Project Management + PSA — hybrid native/framework (Phase P2.10)
    path("api/v1/projects/", include("apps.projects.urls")),
    # Helpdesk + ITSM — framework + reused SLA engine (Phase P2.11)
    path("api/v1/helpdesk/", include("apps.helpdesk.urls")),
    # Manufacturing + MRP — native engine (Phase P2.12)
    path("api/v1/manufacturing/", include("apps.manufacturing.urls")),
    # Analytics + KPI Registry — extends reporting (Phase P2.13)
    path("api/v1/analytics/", include("apps.analytics.urls")),
    # Dependency & Impact Analysis — orchestrates apps.metadata.impact (Phase P2.14)
    path("api/v1/dependency/", include("apps.dependency.urls")),
    # Environment Promotion — orchestrates Config VCS + P2.14 (Phase P2.15)
    path("api/v1/environments/", include("apps.environments.urls")),
    # Enterprise Certification — health, registry, simulations (Phase P2.16)
    path("api/v1/certification/", include("apps.certification.urls")),
    # Credit Engine (F3) — discounts/scholarships/waivers/credit-notes/refunds/write-offs
    path("api/v1/credits/", include("apps.credits.urls")),
    # Collections Engine (F2) — installments/payment-plans/late-fees/reminders/dunning
    path("api/v1/collections/", include("apps.collections_engine.urls")),
    # Tax Engine (G1) — VAT/GST/sales/excise/withholding calc/post/reverse + tax return
    path("api/v1/taxes/", include("apps.taxes.urls")),
    # Revenue Recognition (F5) — deferred revenue / recognition schedules
    path("api/v1/revenue/", include("apps.revenue.urls")),
    # Financial Statements (F6) — trial balance / balance sheet / P&L / cash flow / aging
    path("api/v1/financial-reports/", include("apps.financial_reports.urls")),
    # Settlement / Payment-Allocation — invoice↔payment matching + invoice-matched aging
    path("api/v1/settlement/", include("apps.settlement.urls")),
    # Multi-Currency — currency master, exchange rates, conversion (FX revaluation via service)
    path("api/v1/currency/", include("apps.currency.urls")),
    # Cash Management & Bank Reconciliation (F8) — accounts/transfers/statements/matching
    path("api/v1/cash/", include("apps.cash.urls")),
    # Financial Dimensions (F9) — cost/profit centers, segments (generic dimension framework)
    path("api/v1/dimensions/", include("apps.dimensions.urls")),
    # Budgets & Forecasts (F10) — plans/versions/lines + budget-vs-actual from GL
    path("api/v1/budgets/", include("apps.budgets.urls")),
    # Company platform (F11) — legal entities, tax registrations, ownership
    path("api/v1/companies/", include("apps.companies.urls")),
    # Consolidation & Intercompany (F11) — runs/worksheets, translation, elimination, minority
    path("api/v1/consolidation/", include("apps.consolidation.urls")),
    # Treasury (F12) — counterparties/facilities/investments/transactions, schedules, liquidity
    path("api/v1/treasury/", include("apps.treasury.urls")),
    # Financial KPI Library (F13) — native finance KPI catalog + evaluators + dashboard templates
    path("api/v1/financial-kpis/", include("apps.financial_kpis.urls")),
    # System-Entity Adapter (B0) — native-model engines rendered by the Generic Runtime
    path("api/v1/system-entities/", include("apps.system_entities.urls")),
    # Marketplace / plugins
    path("api/v1/marketplace/", include("apps.marketplace.urls")),
    # Solution Package Platform (registry / preflight / lifecycle)
    path("api/v1/packages/", include("apps.packaging.urls")),
    # Business rules
    path("api/v1/rules/", include("apps.rules.urls")),
    # Approvals
    path("api/v1/approvals/", include("apps.approvals.urls")),
    # SLA
    path("api/v1/sla/", include("apps.sla.urls")),
    # Recycle bin
    path("api/v1/recyclebin/", include("apps.recyclebin.urls")),
    # Data import / export (staging app; the bare /staging/ mount was empty and removed)
    path("api/v1/import/", include("apps.staging.urls_import")),
    path("api/v1/export/", include("apps.staging.urls_export")),
    # Integrations (outbound webhooks, connectors, OAuth apps, inbound webhooks)
    path("api/v1/integrations/", include("apps.integrations.urls")),
    path("api/v1/webhooks/", include("apps.integrations.urls_webhooks")),
    # Branding & Localization
    path("api/v1/branding/", include("apps.branding.urls")),
    path("api/v1/localization/", include("apps.localization.urls")),
    # Tagging
    path("api/v1/tags/", include("apps.tagging.urls")),
    # Saved views
    path("api/v1/saved-views/", include("apps.views_saved.urls")),
    # Public forms
    path("api/v1/public-forms/", include("apps.public_forms.urls")),
    # Portal
    path("api/v1/portal/", include("apps.portal.urls")),
    # Custom-admin Portal Builder (member-authenticated; outside the exempt /portal/ realm)
    path("api/v1/portal-admin/", include("apps.portal.admin_urls")),
    # Custom admin
    path("api/v1/admin/", include("apps.admin_views.urls")),
    # Data lineage
    path("api/v1/lineage/", include("apps.lineage.urls")),
    # Schema Registry (entity / field definitions)
    path("api/v1/schema/", include("apps.schema_registry.urls")),
    # OpenAPI schema
    path("api/openapi/", SpectacularAPIView.as_view(), name="schema"),
    path("api/openapi/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/openapi/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
