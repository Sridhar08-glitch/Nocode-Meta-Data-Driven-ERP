"""
Analytics / KPI Registry models (Phase P2.13).

The ONE genuine gap over the existing reporting stack: a centralized **KPI Registry** so every KPI
is defined once and reused everywhere (no report defines KPIs independently). Everything else —
reports, dashboards, NQL, snapshots, CSV/XLSX/PDF, scheduling — is REUSED from ``apps/reporting``;
this app never re-implements a query/export/scheduler engine. KPISnapshot preserves historical KPI
values (month/quarter/year-end). Workspace-scoped (TenantModel) + RLS (migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

NUM = {"max_digits": 20, "decimal_places": 4, "default": 0}


class KPIDefinition(TenantModel):
    """A reusable KPI. ``source_type`` is ``nql`` (aggregate an NQL query over a metadata entity)
    or ``native`` (a registered cross-module evaluator, e.g. inventory value / payroll cost)."""
    code = models.SlugField(max_length=64)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=40, default="general")
    # financial | crm | projects | hr | payroll | procurement | inventory | manufacturing |
    # assets | helpdesk | accounting | operations | general
    source_type = models.CharField(max_length=10, default="nql")   # nql | native
    nql_source = models.TextField(blank=True)
    value_field = models.CharField(max_length=64, blank=True)
    aggregate = models.CharField(max_length=10, default="sum")      # sum|avg|count|min|max
    native_key = models.CharField(max_length=64, blank=True)
    target = models.DecimalField(**NUM)
    warning_threshold = models.DecimalField(**NUM)
    critical_threshold = models.DecimalField(**NUM)
    direction = models.CharField(max_length=15, default="higher_better")  # higher_better|lower_better
    unit = models.CharField(max_length=20, blank=True)
    owner = models.CharField(max_length=64, blank=True)
    refresh_strategy = models.CharField(max_length=15, default="on_demand")  # on_demand|daily|...
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = "analytics_kpi_definitions"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "category", "is_active"])]


class KPISnapshot(TenantModel):
    """Point-in-time KPI value for historical preservation + trend analysis."""
    kpi_id = models.UUIDField(db_index=True)
    code = models.SlugField(max_length=64)
    value = models.DecimalField(**NUM)
    target = models.DecimalField(**NUM)
    status = models.CharField(max_length=15, default="unknown")  # good|warning|critical|unknown
    period = models.CharField(max_length=20, blank=True)         # e.g. 2026-06 / Q2-2026

    class Meta:
        db_table = "analytics_kpi_snapshots"
        indexes = [models.Index(fields=["workspace_id", "code", "-created_at"])]
