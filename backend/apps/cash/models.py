"""
Cash Management & Bank Reconciliation (Financial Platform — F8) — the generic, reusable Core capability
for bank/cash accounts, transfers, cash instruments (cheques/deposits/EFT), bank-statement import and
deterministic reconciliation against the GL.

PLATFORM engine, not a package feature (Rule 20): every ERP package (Hospital/Hotel/Retail/Government/…)
consumes THIS — none ships a cash or reconciliation module. GL OWNERSHIP is preserved: reconciliation is
a MATCHING sub-ledger that REFERENCES GL journal lines (by id) and posts NO accounting; the only GL
posting is a real cash movement (``bank_transfer`` → GLBus). Generalization: cash accounts are
``bank_account(account_type=cash)``; cheques/deposits/EFT are ``cash_instrument(instrument_type)``;
cash transactions are GL journal lines (not re-stored); outstanding items are DERIVED (unmatched lines).
Workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 20, "decimal_places": 2, "default": 0}

# Money flowing INTO our account (deposit/receipt) vs OUT (payment/withdrawal).
IN = "in"
OUT = "out"
DIRECTIONS = [(IN, "In (receipt)"), (OUT, "Out (payment)")]


class BankAccount(TenantModel):
    """A bank / cash / mobile-money account — the operational layer over a GL cash control account.
    ``account_type=cash`` is a petty-cash box (no bank details); no separate cash_account entity."""

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=16, default="bank", choices=[
        ("bank", "Bank"), ("cash", "Cash"), ("mobile_money", "Mobile Money"),
        ("card", "Card"), ("other", "Other")])
    bank_name = models.CharField(max_length=200, blank=True)
    account_number = models.CharField(max_length=64, blank=True)
    iban = models.CharField(max_length=64, blank=True)
    swift = models.CharField(max_length=32, blank=True)
    gl_account_code = models.CharField(max_length=32, blank=True)   # the GL cash account it maps to
    currency = models.CharField(max_length=3, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "cash_bank_accounts"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "code"]),
                   models.Index(fields=["workspace_id", "gl_account_code"])]

    def __str__(self):
        return f"{self.code} {self.name}"


class BankStatement(TenantModel):
    """An imported bank statement for one account + period."""

    IMPORTED = "imported"
    RECONCILING = "reconciling"
    RECONCILED = "reconciled"
    STATUS_CHOICES = [(IMPORTED, "Imported"), (RECONCILING, "Reconciling"),
                      (RECONCILED, "Reconciled")]

    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="statements")
    statement_ref = models.CharField(max_length=64, blank=True)
    statement_date = models.DateField(null=True, blank=True)
    opening_balance = models.DecimalField(**MONEY)
    closing_balance = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, blank=True)
    external_ref = models.CharField(max_length=160, blank=True, db_index=True)  # idempotency
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=IMPORTED)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "bank_statements"
        indexes = [models.Index(fields=["workspace_id", "bank_account", "statement_date"]),
                   models.Index(fields=["workspace_id", "external_ref"])]

    def __str__(self):
        return f"{self.statement_ref} {self.closing_balance}"


class BankStatementLine(TenantModel):
    """One bank transaction on a statement (bank side of reconciliation)."""

    UNMATCHED = "unmatched"
    MATCHED = "matched"
    IGNORED = "ignored"
    STATUS_CHOICES = [(UNMATCHED, "Unmatched"), (MATCHED, "Matched"), (IGNORED, "Ignored")]

    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name="lines")
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="stmt_lines")
    line_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(**MONEY)                           # positive
    direction = models.CharField(max_length=4, choices=DIRECTIONS, default=IN)
    reference = models.CharField(max_length=128, blank=True)
    description = models.CharField(max_length=255, blank=True)
    counterparty = models.CharField(max_length=200, blank=True)
    matched_amount = models.DecimalField(**MONEY)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=UNMATCHED)

    class Meta:
        db_table = "bank_statement_lines"
        indexes = [models.Index(fields=["workspace_id", "statement", "status"]),
                   models.Index(fields=["workspace_id", "bank_account", "line_date"])]

    def __str__(self):
        return f"{self.line_date} {self.direction} {self.amount}"

    @property
    def signed(self):
        return self.amount if self.direction == IN else -self.amount


class BankReconciliation(TenantModel):
    """A reconciliation session for a bank account up to a date — reconciles the GL book balance to
    the statement closing balance via matches + outstanding items."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    RECONCILED = "reconciled"
    STATUS_CHOICES = [(DRAFT, "Draft"), (IN_PROGRESS, "In Progress"), (RECONCILED, "Reconciled")]

    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE,
                                     related_name="reconciliations")
    statement = models.ForeignKey(BankStatement, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="reconciliations")
    reconciliation_date = models.DateField(null=True, blank=True)
    book_balance = models.DecimalField(**MONEY)                    # GL cash-account balance
    statement_balance = models.DecimalField(**MONEY)              # statement closing balance
    reconciled_balance = models.DecimalField(**MONEY)            # book adjusted for outstanding items
    difference = models.DecimalField(**MONEY)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=DRAFT)
    reconciled_by = models.UUIDField(null=True, blank=True)
    reconciled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "bank_reconciliations"
        indexes = [models.Index(fields=["workspace_id", "bank_account", "status"])]

    def __str__(self):
        return f"recon {self.bank_account_id} {self.reconciliation_date}"


class ReconciliationMatch(TenantModel):
    """One match linking a bank-statement line to a GL journal line (referenced by id — GL stays the
    single owner of accounting). Split/partial → multiple rows; ``match_type`` records how it matched."""

    reconciliation = models.ForeignKey(BankReconciliation, on_delete=models.CASCADE,
                                       related_name="matches")
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="matches")
    statement_line = models.ForeignKey(BankStatementLine, null=True, blank=True,
                                       on_delete=models.CASCADE, related_name="matches")
    journal_line_id = models.UUIDField(null=True, blank=True)     # GL JournalLine (soft ref)
    amount = models.DecimalField(**MONEY)
    match_type = models.CharField(max_length=12, default="exact", choices=[
        ("exact", "Exact"), ("reference", "Reference"), ("tolerance", "Tolerance"),
        ("partial", "Partial"), ("manual", "Manual")])
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "reconciliation_matches"
        indexes = [models.Index(fields=["workspace_id", "reconciliation"]),
                   models.Index(fields=["workspace_id", "journal_line_id"]),
                   models.Index(fields=["workspace_id", "statement_line"])]

    def __str__(self):
        return f"match {self.amount} ({self.match_type})"


class BankTransfer(TenantModel):
    """A transfer between own bank/cash accounts (transfer_type absorbs cash↔bank). A REAL cash
    movement → posts ONE GL entry (Dr destination cash / Cr source cash) through GLBus (no duplicate
    accounting; GL stays the owner)."""

    DRAFT = "draft"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [(DRAFT, "Draft"), (COMPLETED, "Completed"), (CANCELLED, "Cancelled")]

    number = models.CharField(max_length=64, blank=True)
    transfer_type = models.CharField(max_length=16, default="bank_to_bank", choices=[
        ("bank_to_bank", "Bank to Bank"), ("cash_to_bank", "Cash to Bank"),
        ("bank_to_cash", "Bank to Cash"), ("cash_to_cash", "Cash to Cash")])
    from_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT,
                                     related_name="transfers_out")
    to_account = models.ForeignKey(BankAccount, on_delete=models.PROTECT,
                                   related_name="transfers_in")
    amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, blank=True)
    transfer_date = models.DateField(null=True, blank=True)
    memo = models.CharField(max_length=255, blank=True)
    external_ref = models.CharField(max_length=160, blank=True, db_index=True)
    journal_entry_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "bank_transfers"
        indexes = [models.Index(fields=["workspace_id", "status"]),
                   models.Index(fields=["workspace_id", "external_ref"])]

    def __str__(self):
        return f"{self.number} {self.amount}"


class CashInstrument(TenantModel):
    """A cash instrument in transit — cheque (issued/received), deposit slip, EFT/wire, card or mobile
    settlement. ``instrument_type`` absorbs all of them (no deposit/cheque/EFT entities). Tracking-only
    (no GL — the underlying payment already posted); a clearing/bounce is a status transition."""

    PENDING = "pending"
    DEPOSITED = "deposited"
    CLEARED = "cleared"
    BOUNCED = "bounced"
    CANCELLED = "cancelled"
    STATUS_CHOICES = [(PENDING, "Pending"), (DEPOSITED, "Deposited"), (CLEARED, "Cleared"),
                      (BOUNCED, "Bounced"), (CANCELLED, "Cancelled")]

    number = models.CharField(max_length=64, blank=True)
    instrument_type = models.CharField(max_length=20, default="cheque_received", choices=[
        ("cheque_issued", "Cheque Issued"), ("cheque_received", "Cheque Received"),
        ("deposit", "Deposit"), ("eft", "EFT"), ("wire", "Wire"), ("card", "Card"),
        ("mobile_money", "Mobile Money")])
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="instruments")
    amount = models.DecimalField(**MONEY)
    direction = models.CharField(max_length=4, choices=DIRECTIONS, default=IN)
    reference = models.CharField(max_length=128, blank=True)      # cheque no / txn reference
    counterparty = models.CharField(max_length=200, blank=True)
    partner_ref = models.CharField(max_length=128, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    clearing_date = models.DateField(null=True, blank=True)
    journal_entry_id = models.UUIDField(null=True, blank=True)    # optional link to its GL posting
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "cash_instruments"
        indexes = [models.Index(fields=["workspace_id", "bank_account", "status"]),
                   models.Index(fields=["workspace_id", "instrument_type", "status"])]

    def __str__(self):
        return f"{self.instrument_type} {self.reference} {self.amount}"
