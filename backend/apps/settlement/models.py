"""
Settlement / Payment-Allocation engine (Financial Platform — Gap: settlement) — the generic, reusable
Core capability that MATCHES credits (payments / credit-notes / deposits / advances) to debits
(invoices / charges / debit-notes) so a receivable/payable can be partially, split- or fully settled,
and so aging can be reported against the UNSETTLED portion of each document (invoice-matched).

This is a PLATFORM engine (Rule 20). It is a SUB-LEDGER matching layer — allocation itself posts NO
GL (the invoice and the payment already posted to the AR/AP control account through ``GLBus``; the net
control balance is already correct). Settlement records WHICH payment settles WHICH invoice, tracks the
outstanding per document, and enables invoice-matched aging + statements. Optional residual write-off
reuses the Credit Engine (never new GL). Workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 20, "decimal_places": 2, "default": 0}

# Direction on the partner control account: a DEBIT increases what the partner owes us (receivable) /
# what we owe (payable target); a CREDIT reduces it (a payment/credit/deposit).
DEBIT = "debit"
CREDIT = "credit"
DIRECTIONS = [(DEBIT, "Debit (owed — invoice/charge)"), (CREDIT, "Credit (paying — payment/credit)")]

DOC_TYPES = [
    ("invoice", "Invoice"), ("charge", "Charge"), ("debit_note", "Debit Note"),
    ("payment", "Payment"), ("credit_note", "Credit Note"), ("deposit", "Deposit"),
    ("advance", "Advance"), ("refund", "Refund"),
]


class SettlementDocument(TenantModel):
    """One open item in the settlement sub-ledger — an amount owed (debit) or paying (credit) for a
    partner. ``outstanding`` = ``amount − allocated_amount``; ``status`` follows the allocation."""

    OPEN = "open"
    PARTIAL = "partial"
    SETTLED = "settled"
    VOID = "void"
    STATUS_CHOICES = [(OPEN, "Open"), (PARTIAL, "Partial"), (SETTLED, "Settled"), (VOID, "Void")]

    partner_ref = models.CharField(max_length=128)
    direction = models.CharField(max_length=8, choices=DIRECTIONS)
    doc_type = models.CharField(max_length=16, choices=DOC_TYPES, default="invoice")

    document_ref = models.CharField(max_length=128, blank=True)   # source doc id / number
    document_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    amount = models.DecimalField(**MONEY)                         # original (positive)
    allocated_amount = models.DecimalField(**MONEY)              # settled so far
    account_code = models.CharField(max_length=32, blank=True)   # the AR/AP control account
    currency = models.CharField(max_length=3, blank=True)

    source_module = models.CharField(max_length=50, blank=True)
    external_ref = models.CharField(max_length=160, blank=True, db_index=True)  # idempotency
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=OPEN)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "settlement_documents"
        indexes = [
            models.Index(fields=["workspace_id", "partner_ref", "direction", "status"]),
            models.Index(fields=["workspace_id", "external_ref"]),
            models.Index(fields=["workspace_id", "document_date"]),
        ]

    def __str__(self):
        return f"{self.doc_type} {self.document_ref} {self.amount}"

    @property
    def outstanding(self):
        return self.amount - self.allocated_amount


class Allocation(TenantModel):
    """Links a CREDIT document (paying) to a DEBIT document (owed) for an amount — the atomic act of
    settlement. Immutable; a correction is ``unallocate`` (which deletes it and restores balances)."""

    credit_document = models.ForeignKey(SettlementDocument, on_delete=models.CASCADE,
                                        related_name="allocations_from")
    debit_document = models.ForeignKey(SettlementDocument, on_delete=models.CASCADE,
                                       related_name="allocations_to")
    amount = models.DecimalField(**MONEY)
    external_ref = models.CharField(max_length=160, blank=True, db_index=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "settlement_allocations"
        indexes = [
            models.Index(fields=["workspace_id", "credit_document"]),
            models.Index(fields=["workspace_id", "debit_document"]),
        ]

    def __str__(self):
        return f"{self.credit_document_id}→{self.debit_document_id} {self.amount}"
