"""
Revenue Recognition engine (Financial Platform — F5 / Gap G5) — the generic, reusable Core capability
for DEFERRED REVENUE + ACCRUAL: recognise revenue over time from a deferred liability into earned
revenue on a schedule, posting each recognition through the single GL.

This is a PLATFORM engine, not a package feature (Rule 20): a package bills a document (Dr A/R, Cr
Deferred Revenue 2400) and declares a schedule; ``RevenueService`` then recognises each period
(Dr Deferred Revenue, Cr Earned Revenue) via ``GLBus`` — NO package re-implements recognition. A
correction is a schedule ``cancel`` (a GL reversal of recognised periods), never an edit. Workspace-
scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 20, "decimal_places": 2, "default": 0}

# Recognition method — how the total is spread across periods.
IMMEDIATE = "immediate"          # recognise the whole amount at once
STRAIGHT_LINE = "straight_line"  # equal amounts over N periods
MILESTONE = "milestone"          # caller supplies per-period amounts
METHODS = [(IMMEDIATE, "Immediate"), (STRAIGHT_LINE, "Straight Line"), (MILESTONE, "Milestone")]


class RevenueSchedule(TenantModel):
    """A deferred-revenue recognition plan for one source document."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [(ACTIVE, "Active"), (COMPLETED, "Completed"), (CANCELLED, "Cancelled")]

    number = models.CharField(max_length=64, blank=True)
    source_module = models.CharField(max_length=50, blank=True)
    source_ref = models.CharField(max_length=128, blank=True)
    external_ref = models.CharField(max_length=160, blank=True, db_index=True)  # idempotency
    partner_ref = models.CharField(max_length=128, blank=True)

    method = models.CharField(max_length=16, choices=METHODS, default=STRAIGHT_LINE)
    total_amount = models.DecimalField(**MONEY)
    recognized_amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, blank=True)
    num_periods = models.PositiveIntegerField(default=1)
    start_date = models.DateField(null=True, blank=True)
    frequency = models.CharField(max_length=12, default="monthly")  # monthly / weekly / daily

    # GL accounts (resolved from AccountingSettings; override-able). Deferred = the liability the
    # billing set up; revenue = the earned-revenue account each period credits.
    deferred_account = models.CharField(max_length=32)
    revenue_account = models.CharField(max_length=32)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "revenue_schedules"
        indexes = [
            models.Index(fields=["workspace_id", "status"]),
            models.Index(fields=["workspace_id", "source_module", "source_ref"]),
            models.Index(fields=["workspace_id", "external_ref"]),
        ]

    def __str__(self):
        return f"{self.number or self.source_ref} {self.total_amount}"


class RevenueScheduleLine(TenantModel):
    """One period's recognition. Immutable once recognised (posts a GL entry)."""

    schedule = models.ForeignKey(RevenueSchedule, on_delete=models.CASCADE, related_name="lines")
    period_no = models.PositiveIntegerField(default=1)
    period_date = models.DateField()
    amount = models.DecimalField(**MONEY)
    recognized = models.BooleanField(default=False)
    journal_entry_id = models.UUIDField(null=True, blank=True)
    recognized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "revenue_schedule_lines"
        indexes = [
            models.Index(fields=["workspace_id", "schedule", "period_no"]),
            models.Index(fields=["workspace_id", "recognized", "period_date"]),
        ]

    def __str__(self):
        return f"{self.schedule_id}[{self.period_no}] {self.amount}"
