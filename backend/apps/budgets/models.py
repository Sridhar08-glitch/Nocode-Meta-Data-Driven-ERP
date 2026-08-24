"""
Budgets & Forecasts (Financial Platform — F10) — the generic, reusable Core capability for planning:
budgets AND forecasts, with scenarios, versions/revisions, rolling forecasts, dimensioned lines and
budget-vs-actual / forecast-vs-actual against the GL.

GENERALIZATION (6/7-point): a budget and a forecast are the SAME structure (planned amounts by account
× dimension × period, evolving through versions/scenarios) — so there is ONE ``FinancialPlan``
(``plan_type`` discriminator) + ``PlanVersion`` (the scenario + revision axis: ``budget_revision`` /
``snapshot`` / ``adjustment`` / ``scenario`` all collapse here) + ``PlanLine`` (the atomic budgeted
amount, tagged with F9 ``dimensions``). Variance/allocation are COMPUTED/service, not entities; actuals
come ONLY from GL (no duplicated accounting). Workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 20, "decimal_places": 2, "default": 0}

BUDGET = "budget"
FORECAST = "forecast"
PLAN_TYPES = [(BUDGET, "Budget"), (FORECAST, "Forecast")]


class FinancialPlan(TenantModel):
    """A budget or forecast definition for a fiscal cycle. ``plan_type`` is the only thing that
    distinguishes a budget from a forecast — the mechanics are identical."""

    DRAFT = "draft"
    ACTIVE = "active"
    LOCKED = "locked"
    ARCHIVED = "archived"
    STATUS_CHOICES = [(DRAFT, "Draft"), (ACTIVE, "Active"), (LOCKED, "Locked"),
                      (ARCHIVED, "Archived")]

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=200)
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPES, default=BUDGET)
    fiscal_year = models.CharField(max_length=16, blank=True)      # "FY2026"
    period_type = models.CharField(max_length=10, default="monthly", choices=[
        ("monthly", "Monthly"), ("quarterly", "Quarterly"), ("annual", "Annual")])
    currency = models.CharField(max_length=3, blank=True)
    is_rolling = models.BooleanField(default=False)               # rolling forecast
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "financial_plans"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "plan_type", "status"]),
                   models.Index(fields=["workspace_id", "fiscal_year"])]

    def __str__(self):
        return f"{self.code} {self.name}"


class PlanVersion(TenantModel):
    """A version of a plan under a scenario — the revision + scenario axis. ``(scenario, version_no)``
    identifies a revision; ``is_current`` marks the active version per scenario. Approval carries
    segregation of duties (approver ≠ creator); a ``locked`` version is immutable."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    LOCKED = "locked"
    STATUS_CHOICES = [(DRAFT, "Draft"), (SUBMITTED, "Submitted"), (APPROVED, "Approved"),
                      (LOCKED, "Locked")]

    plan = models.ForeignKey(FinancialPlan, on_delete=models.CASCADE, related_name="versions")
    version_no = models.PositiveIntegerField(default=1)
    scenario = models.CharField(max_length=16, default="baseline", choices=[
        ("baseline", "Baseline"), ("working", "Working"), ("optimistic", "Optimistic"),
        ("pessimistic", "Pessimistic"), ("committed", "Committed")])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    revision_note = models.CharField(max_length=500, blank=True)
    is_current = models.BooleanField(default=True)
    submitted_by = models.UUIDField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "plan_versions"
        unique_together = [("workspace_id", "plan", "scenario", "version_no")]
        indexes = [models.Index(fields=["workspace_id", "plan", "scenario", "is_current"])]

    def __str__(self):
        return f"{self.plan_id} {self.scenario} v{self.version_no}"


class PlanLine(TenantModel):
    """One budgeted/forecast amount — an account × dimensions × period cell. ``dimensions`` reuses the
    F9 framework ({dimension_code: value_code}); actuals for this line come from the GL filtered by the
    same account + dimensions + period."""

    version = models.ForeignKey(PlanVersion, on_delete=models.CASCADE, related_name="lines")
    account_code = models.CharField(max_length=32)               # the GL account budgeted
    dimensions = models.JSONField(default=dict, blank=True)      # F9 {dimension_code: value_code}
    period = models.CharField(max_length=16, blank=True)         # "2026-01" / "FY2026"
    period_date = models.DateField(null=True, blank=True)        # for actual-matching (period start)
    amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "plan_lines"
        indexes = [models.Index(fields=["workspace_id", "version", "account_code"]),
                   models.Index(fields=["workspace_id", "version", "period_date"])]

    def __str__(self):
        return f"{self.account_code} {self.period} {self.amount}"
