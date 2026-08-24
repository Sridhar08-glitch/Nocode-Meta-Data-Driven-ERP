"""
Numbering Engine (Phase P2.1) — the gapless, tenant-isolated, concurrency-safe document
number service every finance/ops module builds on (invoices, POs, SOs, journal entries,
employee codes, …). ``auto_number`` metadata fields are NOT gapless under concurrency; this
engine guarantees a serialized, audited, resettable sequence per ``(workspace, key)``.

Both tables are workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel


class NumberSequence(TenantModel):
    """A named counter. One row per ``(workspace_id, key)``; the counter is advanced under a
    ``SELECT … FOR UPDATE`` row lock so concurrent allocations can never collide or skip."""

    RESET_NEVER = "never"
    RESET_YEARLY = "yearly"
    RESET_MONTHLY = "monthly"
    RESET_DAILY = "daily"
    RESET_CHOICES = [
        (RESET_NEVER, "Never"),
        (RESET_YEARLY, "Yearly"),
        (RESET_MONTHLY, "Monthly"),
        (RESET_DAILY, "Daily"),
    ]

    key = models.SlugField(max_length=100)               # "invoice", "sales_order", "journal_entry"
    name = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)

    prefix = models.CharField(max_length=40, blank=True)     # "INV-"
    suffix = models.CharField(max_length=40, blank=True)
    padding = models.PositiveSmallIntegerField(default=6)    # zero-pad width → 000001
    start_value = models.BigIntegerField(default=1)
    increment = models.PositiveIntegerField(default=1)

    reset_scope = models.CharField(max_length=10, choices=RESET_CHOICES, default=RESET_NEVER)
    # When True the period token (e.g. "2026" / "2026-06") is embedded in the formatted number.
    include_period_in_format = models.BooleanField(default=False)

    # Mutable counter state (advanced atomically by the service).
    current_value = models.BigIntegerField(default=0)        # last value ISSUED in current period
    period_key = models.CharField(max_length=16, blank=True)  # current period token
    initialized = models.BooleanField(default=False)         # has any number been issued yet?

    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)           # auto-registered by an engine
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "number_sequences"
        unique_together = [("workspace_id", "key")]
        indexes = [models.Index(fields=["workspace_id", "key"])]

    def __str__(self):
        return f"{self.key} → {self.prefix}{'#' * self.padding}{self.suffix}"


class NumberAllocation(TenantModel):
    """Append-only audit log of every issued number — the gapless trail. Each row records the
    formatted value, the raw integer, the period, who/what consumed it, and a free-form context
    (source module/ref) so an allocation can always be traced back to its document."""

    sequence = models.ForeignKey(
        NumberSequence, on_delete=models.CASCADE, related_name="allocations")
    key = models.SlugField(max_length=100)
    formatted = models.CharField(max_length=128)
    value = models.BigIntegerField()
    period_key = models.CharField(max_length=16, blank=True)
    context = models.JSONField(default=dict, blank=True)     # {"source_module": "...", "source_ref": "..."}
    allocated_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "number_allocations"
        indexes = [
            models.Index(fields=["workspace_id", "key"]),
            models.Index(fields=["workspace_id", "sequence"]),
        ]

    def __str__(self):
        return self.formatted
