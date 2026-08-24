"""
Tax Engine (Financial Platform — Gap G1) — the generic, reusable Core capability every ERP package
consumes for INDIRECT + WITHHOLDING tax: VAT / GST / sales tax / excise / service tax / withholding.

This is a PLATFORM engine, not a package feature (Rule 20 / BILLING_REFERENCE_ARCHITECTURE): Hospital,
Hotel, Retail, Construction, Government, Education, Manufacturing, Logistics — every package — declares
BUSINESS EVENTS and calls the platform actions (``action_calculate_tax`` / ``action_post_tax`` /
``action_reverse_tax``); NONE re-implements tax logic. Tax mechanics live HERE and post through the
single GL (``GLBus``), number through ``NumberingService`` and record an immutable tax subledger
(``TaxTransaction``) for tax returns. Corrections are a ``reverse`` (a GL reversal), never an edit.

Model (all workspace-scoped ``TenantModel`` + RLS migration 0002):
  TaxAuthority  — the taxing body / jurisdiction (VAT office, IRS, state).
  TaxCode       — a stable tax definition (type, inclusive/compound flags, GL accounts). Rates are
                  TEMPORAL, held in TaxRate (a rate changes over time; history is preserved).
  TaxRate       — the effective rate of a TaxCode over a date range (the enterprise rate history).
  TaxGroup      — an ordered bundle of TaxCodes applied together (compound / multiple taxes).
  TaxGroupMember— one code in a group (ordered).
  TaxExemption  — a partner's exemption / certificate for a code or group over a date range.
  TaxTransaction— the IMMUTABLE computed tax record (the tax subledger for returns / audit).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 20, "decimal_places": 2, "default": 0}
RATE = {"max_digits": 12, "decimal_places": 6, "default": 0}

# Tax type taxonomy (generic — every jurisdiction's tax maps to one of these).
TAX_TYPES = [
    ("vat", "VAT"),
    ("gst", "GST"),
    ("sales_tax", "Sales Tax"),
    ("excise", "Excise"),
    ("service_tax", "Service Tax"),
    ("withholding", "Withholding Tax"),
    ("custom", "Custom / Other"),
]

# Rounding policy per code (generic; default banker-safe half-up matching the ledger).
ROUNDING_CHOICES = [("half_up", "Half Up"), ("half_down", "Half Down"), ("half_even", "Half Even")]

# Direction of a tax transaction: output = collected on sales (liability); input = paid on purchases
# (recoverable asset). Withholding is a special output/input depending on the flow.
OUTPUT = "output"
INPUT = "input"
DIRECTIONS = [(OUTPUT, "Output (collected)"), (INPUT, "Input (paid/recoverable)")]


class TaxAuthority(TenantModel):
    """The taxing body / jurisdiction a tax is remitted to."""

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=2, blank=True)          # ISO-3166 alpha-2
    level = models.CharField(max_length=16, blank=True)           # federal/national/state/local
    registration_no = models.CharField(max_length=64, blank=True)  # the org's tax registration
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "tax_authorities"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "code"])]

    def __str__(self):
        return f"{self.code} {self.name}"


class TaxCode(TenantModel):
    """A stable tax definition. The RATE is temporal (see ``TaxRate``) — a code's percentage changes
    over time while the code, type, accounts and inclusive/compound behaviour stay constant.

    ``is_inclusive`` — prices are tax-inclusive by default (gross given, net + tax derived).
    ``is_compound`` — this tax applies ON TOP of prior taxes in a group (cascading), not just the net.
    ``is_recoverable`` — input tax is reclaimable (posts to a recoverable ASSET), else it is a cost.
    """

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=200)
    authority = models.ForeignKey(TaxAuthority, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="codes")
    tax_type = models.CharField(max_length=16, choices=TAX_TYPES, default="vat")
    is_inclusive = models.BooleanField(default=False)
    is_compound = models.BooleanField(default=False)
    is_recoverable = models.BooleanField(default=True)
    is_withholding = models.BooleanField(default=False)
    rounding = models.CharField(max_length=10, choices=ROUNDING_CHOICES, default="half_up")

    # GL account codes (resolved from these first, else AccountingSettings defaults). Output = the
    # liability the collected tax sits in; input = the recoverable asset for tax paid.
    output_account_code = models.CharField(max_length=32, blank=True)
    input_account_code = models.CharField(max_length=32, blank=True)

    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "tax_codes"
        unique_together = [("workspace_id", "code")]
        indexes = [
            models.Index(fields=["workspace_id", "code"]),
            models.Index(fields=["workspace_id", "tax_type"]),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"


class TaxRate(TenantModel):
    """The effective rate (PERCENT) of a ``TaxCode`` over a date range. A rate change is a NEW row —
    history is preserved so historical documents recompute at the rate that applied on their date."""

    tax_code = models.ForeignKey(TaxCode, on_delete=models.CASCADE, related_name="rates")
    rate = models.DecimalField(**RATE)                            # 15 → 15%
    effective_from = models.DateField(null=True, blank=True)      # null → always-from
    effective_to = models.DateField(null=True, blank=True)        # null → open-ended
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "tax_rates"
        indexes = [
            models.Index(fields=["workspace_id", "tax_code", "effective_from"]),
        ]

    def __str__(self):
        return f"{self.tax_code_id} @ {self.rate}%"


class TaxGroup(TenantModel):
    """An ordered bundle of tax codes applied together (compound / multiple taxes on one base)."""

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "tax_groups"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "code"])]

    def __str__(self):
        return f"{self.code} {self.name}"


class TaxGroupMember(TenantModel):
    """One tax code within a group, in application order."""

    tax_group = models.ForeignKey(TaxGroup, on_delete=models.CASCADE, related_name="members")
    tax_code = models.ForeignKey(TaxCode, on_delete=models.CASCADE, related_name="group_members")
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "tax_group_members"
        indexes = [models.Index(fields=["workspace_id", "tax_group", "sequence"])]

    def __str__(self):
        return f"{self.tax_group_id}[{self.sequence}] {self.tax_code_id}"


class TaxExemption(TenantModel):
    """A partner's exemption / certificate for a code (or a whole group) over a date range. When it
    matches, the tax component is computed at ZERO (and recorded exempt for the return)."""

    partner_ref = models.CharField(max_length=128)               # opaque partner record id
    tax_code = models.ForeignKey(TaxCode, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name="exemptions")
    tax_group = models.ForeignKey(TaxGroup, null=True, blank=True, on_delete=models.CASCADE,
                                  related_name="exemptions")
    certificate_no = models.CharField(max_length=64, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "tax_exemptions"
        indexes = [
            models.Index(fields=["workspace_id", "partner_ref"]),
        ]

    def __str__(self):
        return f"exempt {self.partner_ref}"


class TaxTransaction(TenantModel):
    """The IMMUTABLE computed tax record — the tax subledger used for tax returns / audit. One row per
    tax component of a source document. A correction is a ``reverse`` (never an edit)."""

    COMPUTED = "computed"
    POSTED = "posted"
    REVERSED = "reversed"
    STATUS_CHOICES = [(COMPUTED, "Computed"), (POSTED, "Posted"), (REVERSED, "Reversed")]

    source_module = models.CharField(max_length=50, blank=True)  # "hospital", "hotel", "retail"…
    source_ref = models.CharField(max_length=128, blank=True)    # the source document id
    tax_code = models.ForeignKey(TaxCode, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="transactions")
    tax_code_str = models.CharField(max_length=32, blank=True)   # denormalized code (survives delete)
    direction = models.CharField(max_length=8, choices=DIRECTIONS, default=OUTPUT)
    taxable_amount = models.DecimalField(**MONEY)
    tax_rate = models.DecimalField(**RATE)
    tax_amount = models.DecimalField(**MONEY)
    is_recoverable = models.BooleanField(default=True)
    is_exempt = models.BooleanField(default=False)
    currency = models.CharField(max_length=3, blank=True)
    partner_ref = models.CharField(max_length=128, blank=True)
    jurisdiction = models.CharField(max_length=64, blank=True)   # authority code (for the return)

    external_ref = models.CharField(max_length=160, blank=True, db_index=True)  # idempotency token
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=COMPUTED)
    journal_entry_id = models.UUIDField(null=True, blank=True)
    reversal_entry_id = models.UUIDField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "tax_transactions"
        indexes = [
            models.Index(fields=["workspace_id", "direction", "status"]),
            models.Index(fields=["workspace_id", "source_module", "source_ref"]),
            models.Index(fields=["workspace_id", "external_ref"]),
        ]

    def __str__(self):
        return f"{self.tax_code_str} {self.direction} {self.tax_amount}"
