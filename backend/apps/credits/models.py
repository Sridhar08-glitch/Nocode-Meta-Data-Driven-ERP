"""
Credit Engine (F3) — the generic, reusable Core capability for reducing or reversing a
receivable: discounts, scholarships, fee waivers, credit notes, refunds, and write-offs.

This is a PLATFORM engine, not a package feature (Rule 20 / BILLING_REFERENCE_ARCHITECTURE):
School (and Hospital, Hotel, Membership, Retail, NGO, …) consume it purely by manifest — a
workflow step or REST call — and never re-implement crediting logic. Every credit is an
IMMUTABLE financial document that posts a balanced entry through the single GL (``GLBus``),
allocates a gapless number (``NumberingService``), and emits a domain event. Corrections are a
``void`` (a GL reversal), never an edit. Workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 16, "decimal_places": 2, "default": 0}

# kind → (debit AccountingSettings field, credit AccountingSettings field). The credit reduces a
# receivable (Cr A/R) against a contra-revenue / expense debit; a refund pays cash (Cr Cash).
KIND_DISCOUNT = "discount"
KIND_SCHOLARSHIP = "scholarship"
KIND_WAIVER = "waiver"
KIND_CREDIT_NOTE = "credit_note"
KIND_REFUND = "refund"
KIND_WRITE_OFF = "write_off"
CREDIT_KINDS = [
    (KIND_DISCOUNT, "Discount"),
    (KIND_SCHOLARSHIP, "Scholarship"),
    (KIND_WAIVER, "Fee Waiver"),
    (KIND_CREDIT_NOTE, "Credit Note"),
    (KIND_REFUND, "Refund"),
    (KIND_WRITE_OFF, "Write-off"),
]

# Which AccountingSettings mapping supplies each side. Resolved at issue time (no hardcoded codes).
KIND_ACCOUNTS = {
    KIND_DISCOUNT: ("default_discount_account", "default_receivable_account"),
    KIND_SCHOLARSHIP: ("default_scholarship_account", "default_receivable_account"),
    KIND_WAIVER: ("default_discount_account", "default_receivable_account"),
    KIND_CREDIT_NOTE: ("default_discount_account", "default_receivable_account"),
    KIND_WRITE_OFF: ("default_writeoff_account", "default_receivable_account"),
    KIND_REFUND: ("default_refund_account", "default_cash_account"),
}

# kind → numbering sequence key + prefix.
KIND_SEQUENCES = {
    KIND_DISCOUNT: ("credit_note", "CN-"),
    KIND_CREDIT_NOTE: ("credit_note", "CN-"),
    KIND_WAIVER: ("credit_note", "CN-"),
    KIND_SCHOLARSHIP: ("scholarship", "SCH-"),
    KIND_WRITE_OFF: ("write_off", "WO-"),
    KIND_REFUND: ("refund", "RF-"),
}


class CreditNote(TenantModel):
    """One immutable credit document. Once ``posted`` it is never modified — a correction is a
    ``void`` (which posts a reversing GL entry)."""

    POSTED = "posted"
    VOID = "void"
    STATUS_CHOICES = [(POSTED, "Posted"), (VOID, "Void")]

    kind = models.CharField(max_length=20, choices=CREDIT_KINDS, default=KIND_DISCOUNT)
    number = models.CharField(max_length=64, blank=True)          # gapless, from NumberingService

    # Generic opaque references (no FK — package-independent, mirrors payroll↔HR by record-id).
    subject_ref = models.CharField(max_length=64, blank=True)     # the customer/student record id
    applies_to_ref = models.CharField(max_length=64, blank=True)  # the invoice/fee document credited

    amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, blank=True)
    reason = models.TextField(blank=True)

    # Resolved GL accounts (from AccountingSettings, override-able per call).
    gl_debit_account = models.CharField(max_length=32)
    gl_credit_account = models.CharField(max_length=32)

    # Caller idempotency token (e.g. "school:invoice:<id>"); blank → ad-hoc issuance.
    external_ref = models.CharField(max_length=128, blank=True, db_index=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=POSTED)
    journal_entry_id = models.UUIDField(null=True, blank=True)
    reversal_entry_id = models.UUIDField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "credit_notes"
        indexes = [
            models.Index(fields=["workspace_id", "kind", "status"]),
            models.Index(fields=["workspace_id", "applies_to_ref"]),
            models.Index(fields=["workspace_id", "subject_ref"]),
            models.Index(fields=["workspace_id", "external_ref"]),
        ]

    def __str__(self):
        return f"{self.number or self.kind} {self.amount}"
