"""
Collections Engine (F2) — the generic, reusable Core capability for turning a receivable into a
schedule of dues and collecting on it: installments, payment plans, due schedules, reminders,
late fees, interest, and dunning.

A PLATFORM engine, not a package feature (Rule 20). School (and Hospital, Membership, Real
Estate, Subscriptions, …) consume it purely by manifest/REST and never re-implement scheduling
or late-fee logic. Payment CASH posting stays with the payment document (the package's
``action_post_journal``); Collections only tracks schedule state and posts the ADDITIONAL late
fee (Dr Receivable / Cr Late-fee income) through the single GL. Workspace-scoped (``TenantModel``
+ RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 16, "decimal_places": 2, "default": 0}

FREQUENCIES = [
    ("weekly", "Weekly"),
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("yearly", "Yearly"),
    ("custom", "Custom (interval_days)"),
]

LATE_FEE_NONE = "none"
LATE_FEE_FLAT = "flat"
LATE_FEE_PERCENT = "percent"
LATE_FEE_TYPES = [
    (LATE_FEE_NONE, "None"),
    (LATE_FEE_FLAT, "Flat amount"),
    (LATE_FEE_PERCENT, "Percent of outstanding"),
]


class InstallmentPlan(TenantModel):
    """A due schedule over a receivable. ``total_amount`` is split into ``num_installments``
    dues from ``start_date`` at ``frequency``."""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [(ACTIVE, "Active"), (COMPLETED, "Completed"), (CANCELLED, "Cancelled")]

    number = models.CharField(max_length=64, blank=True)          # gapless, PLAN-######
    subject_ref = models.CharField(max_length=64, blank=True)     # customer/student record id
    source_document_ref = models.CharField(max_length=64, blank=True)  # the invoice/fee it schedules
    notify_ref = models.CharField(max_length=64, blank=True)      # optional member/portal id for reminders

    total_amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, blank=True)
    num_installments = models.PositiveIntegerField(default=1)
    frequency = models.CharField(max_length=12, choices=FREQUENCIES, default="monthly")
    interval_days = models.PositiveIntegerField(default=0)        # used when frequency="custom"
    start_date = models.DateField()

    # Late-fee / interest policy (applied by the beat, posted through GLBus).
    grace_days = models.PositiveIntegerField(default=0)
    late_fee_type = models.CharField(max_length=8, choices=LATE_FEE_TYPES, default=LATE_FEE_NONE)
    late_fee_value = models.DecimalField(**MONEY)                 # flat amount or percent (e.g. 2.00 = 2%)
    receivable_account = models.CharField(max_length=32, blank=True)
    late_fee_income_account = models.CharField(max_length=32, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    external_ref = models.CharField(max_length=128, blank=True, db_index=True)  # caller idempotency
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "collection_plans"
        indexes = [
            models.Index(fields=["workspace_id", "status"]),
            models.Index(fields=["workspace_id", "subject_ref"]),
            models.Index(fields=["workspace_id", "source_document_ref"]),
            models.Index(fields=["workspace_id", "external_ref"]),
        ]

    def __str__(self):
        return f"{self.number or 'PLAN'} {self.total_amount}"


class Installment(TenantModel):
    """One scheduled due. ``paid_amount`` accrues from ``record_payment``; the beat marks it
    overdue and charges a single late fee past the grace window."""

    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    WAIVED = "waived"
    STATUS_CHOICES = [
        (PENDING, "Pending"), (PARTIAL, "Partial"), (PAID, "Paid"),
        (OVERDUE, "Overdue"), (WAIVED, "Waived"),
    ]

    plan_id = models.UUIDField(db_index=True)
    seq = models.PositiveIntegerField(default=1)
    due_date = models.DateField()
    amount = models.DecimalField(**MONEY)
    paid_amount = models.DecimalField(**MONEY)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)

    late_fee_amount = models.DecimalField(**MONEY)
    late_fee_charged = models.BooleanField(default=False)
    late_fee_journal_entry_id = models.UUIDField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    dunning_level = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "collection_installments"
        unique_together = [("workspace_id", "plan_id", "seq")]
        indexes = [
            models.Index(fields=["workspace_id", "plan_id", "seq"]),
            models.Index(fields=["workspace_id", "status", "due_date"]),
        ]

    def __str__(self):
        return f"#{self.seq} due {self.due_date} {self.amount}"

    @property
    def outstanding(self):
        return self.amount + self.late_fee_amount - self.paid_amount
