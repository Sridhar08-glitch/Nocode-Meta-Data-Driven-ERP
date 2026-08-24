"""
Project Management native models (Phase P2.10).

Only the integrity-critical pieces are native: the project cost ledger (cross-module cost rollup
from payroll/procurement/assets/expenses/timesheets) and project baselines. Projects/tasks/etc.
are framework metadata entities (``blueprint.py``); these reference the project by record-id UUID
(no FK), mirroring payroll↔HR and assets↔asset. Workspace-scoped (TenantModel) + RLS (0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 16, "decimal_places": 2, "default": 0}


class ProjectCostEntry(TenantModel):
    """One cost rolled up to a project from any source. The single source of project actual cost."""
    project_record_id = models.UUIDField(db_index=True)
    source = models.CharField(max_length=20, default="other")
    # payroll | procurement | asset | expense | timesheet | overtime | vendor | other
    description = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(**MONEY)
    entry_date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=128, blank=True)
    posted = models.BooleanField(default=True)
    journal_entry_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "project_cost_entries"
        indexes = [models.Index(fields=["workspace_id", "project_record_id", "source"])]
        # Idempotency backstop (P2.15 Blocker 5): a referenced cost is unique per
        # (workspace, project, source, reference). Blank references (ad-hoc costs) are exempt.
        constraints = [
            models.UniqueConstraint(
                fields=["workspace_id", "project_record_id", "source", "reference"],
                condition=models.Q(reference__gt=""),
                name="uq_project_cost_reference"),
        ]


class ProjectBaseline(TenantModel):
    """Immutable snapshot of a project plan for variance/earned-value tracking."""
    project_record_id = models.UUIDField(db_index=True)
    baseline_date = models.DateField(null=True, blank=True)
    planned_budget = models.DecimalField(**MONEY)
    planned_end_date = models.DateField(null=True, blank=True)
    snapshot = models.JSONField(default=dict)

    class Meta:
        db_table = "project_baselines"
        indexes = [models.Index(fields=["workspace_id", "project_record_id", "-baseline_date"])]
