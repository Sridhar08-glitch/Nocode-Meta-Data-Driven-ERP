"""
General Ledger / posting bus (Phase P2.2) — the double-entry foundation every finance module
posts through. This app owns the GL data model (accounts, fiscal periods, journal entries/lines)
and the posting pipeline that enforces the accounting invariants:

  * every journal entry balances (Σ debits == Σ credits),
  * posted entries are immutable (correction is a reversing entry, never an edit/delete),
  * nothing posts into a closed/locked period.

The Chart-of-Accounts *seeding*, fiscal-year management/close UI, and financial statements
(trial balance / P&L / balance sheet) build on this in P2.3. All tables are workspace-scoped
(``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

# Account classification → natural (normal) balance side.
ASSET = "asset"
LIABILITY = "liability"
EQUITY = "equity"
REVENUE = "revenue"
EXPENSE = "expense"
ACCOUNT_TYPES = [
    (ASSET, "Asset"),
    (LIABILITY, "Liability"),
    (EQUITY, "Equity"),
    (REVENUE, "Revenue"),
    (EXPENSE, "Expense"),
]
DEBIT_NORMAL = {ASSET, EXPENSE}      # these increase with a debit
CREDIT_NORMAL = {LIABILITY, EQUITY, REVENUE}


def normal_balance(account_type: str) -> str:
    return "debit" if account_type in DEBIT_NORMAL else "credit"


class LedgerAccount(TenantModel):
    """A chart-of-accounts node. ``code`` is unique per workspace; ``parent`` enables a tree."""

    code = models.CharField(max_length=32)               # "1000", "4000-01"
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=12, choices=ACCOUNT_TYPES)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="children")
    is_group = models.BooleanField(default=False)        # header/rollup node — not postable
    is_active = models.BooleanField(default=True)
    currency = models.CharField(max_length=3, blank=True)  # blank → workspace default
    description = models.TextField(blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "ledger_accounts"
        unique_together = [("workspace_id", "code")]
        indexes = [
            models.Index(fields=["workspace_id", "code"]),
            models.Index(fields=["workspace_id", "account_type"]),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"

    @property
    def normal_balance(self) -> str:
        return normal_balance(self.account_type)


class Ledger(TenantModel):
    """A set of books for a company (F11 future-proofing). Introduced NOW — additively — so future
    IFRS / Local-GAAP / Tax / Management ledgers are added by creating rows + posting with
    ``JournalEntry.ledger_id``, with NO schema redesign. Today one PRIMARY ledger per company is used;
    ``ledger_id=NULL`` on an entry means the company's primary ledger, so existing books are unchanged."""

    company_id = models.UUIDField(null=True, blank=True, db_index=True)   # → companies.Company
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    ledger_type = models.CharField(max_length=16, default="primary", choices=[
        ("primary", "Primary / Statutory"), ("ifrs", "IFRS"), ("local_gaap", "Local GAAP"),
        ("tax", "Tax"), ("management", "Management")])
    currency = models.CharField(max_length=3, blank=True)
    is_primary = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "ledgers"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "company_id", "is_primary"])]

    def __str__(self):
        return f"{self.code} ({self.ledger_type})"


class AccountingPeriod(TenantModel):
    """A posting window. Entries may only post into an ``open`` period; ``closed`` blocks new
    postings (soft), ``locked`` is permanent (hard close after audit)."""

    OPEN = "open"
    CLOSED = "closed"
    LOCKED = "locked"
    STATUS_CHOICES = [(OPEN, "Open"), (CLOSED, "Closed"), (LOCKED, "Locked")]

    code = models.CharField(max_length=16)               # "2026-06" or "FY2026-P06"
    name = models.CharField(max_length=100, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=OPEN)
    fiscal_year = models.CharField(max_length=16, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "ledger_periods"
        unique_together = [("workspace_id", "code")]
        indexes = [
            models.Index(fields=["workspace_id", "code"]),
            models.Index(fields=["workspace_id", "start_date", "end_date"]),
        ]

    def __str__(self):
        return self.code

    @property
    def is_open(self) -> bool:
        return self.status == self.OPEN


class JournalEntry(TenantModel):
    """A balanced double-entry transaction. ``draft`` entries are editable; once ``posted`` the
    entry + its lines are immutable and only a reversing entry can change the books."""

    DRAFT = "draft"
    POSTED = "posted"
    REVERSED = "reversed"
    STATUS_CHOICES = [(DRAFT, "Draft"), (POSTED, "Posted"), (REVERSED, "Reversed")]

    entry_number = models.CharField(max_length=64, blank=True)  # from the numbering engine
    date = models.DateField()
    period = models.ForeignKey(AccountingPeriod, null=True, blank=True,
                               on_delete=models.PROTECT, related_name="entries")
    memo = models.CharField(max_length=500, blank=True)
    currency = models.CharField(max_length=3, blank=True)

    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=DRAFT)
    # Provenance — which module/record produced this entry (the event-bus trail).
    source_module = models.CharField(max_length=50, blank=True)   # "inventory", "payroll", "manual"
    source_ref = models.CharField(max_length=128, blank=True)     # e.g. a record id / document number
    posting_rule_key = models.CharField(max_length=100, blank=True)

    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.UUIDField(null=True, blank=True)
    # Multi-company (F11) — the legal entity this entry belongs to (a plain UUID → consolidation.Company,
    # no cross-app FK per the TenantModel idiom). Additive + backward-compatible: NULL = the workspace's
    # single/default company, so existing single-company workspaces are byte-identical.
    company_id = models.UUIDField(null=True, blank=True, db_index=True)
    # Multi-ledger (F11) — the set of books this entry posts to (a plain UUID → ledger.Ledger). NULL =
    # the company's PRIMARY ledger, so single-ledger books are unchanged; future IFRS/tax/management
    # ledgers post with an explicit ledger_id (no redesign).
    ledger_id = models.UUIDField(null=True, blank=True, db_index=True)
    # Reversal linkage.
    reverses = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="reversed_by_entries")
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "ledger_journal_entries"
        indexes = [
            models.Index(fields=["workspace_id", "status"]),
            models.Index(fields=["workspace_id", "date"]),
            models.Index(fields=["workspace_id", "source_module", "source_ref"]),
        ]

    def __str__(self):
        return self.entry_number or f"JE {self.id}"


class JournalLine(TenantModel):
    """One debit-or-credit posting against an account. A line carries a non-negative amount on
    exactly one side; the entry is valid only when total debits == total credits."""

    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT, related_name="lines")
    line_no = models.PositiveIntegerField(default=0)
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=0)      # transaction ccy
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=0)     # transaction ccy
    # Multi-currency (additive; backward-compatible): a single-currency (base) line has currency="",
    # fx_rate=1 and base_* == the transaction amount, so existing postings are unchanged. The ledger
    # balances + reports in the BASE currency via base_debit/base_credit.
    currency = models.CharField(max_length=3, blank=True)
    fx_rate = models.DecimalField(max_digits=20, decimal_places=8, default=1)
    base_debit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    base_credit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    memo = models.CharField(max_length=500, blank=True)
    # Optional sub-ledger linkage (a customer/vendor/etc. record this line relates to).
    partner_ref = models.CharField(max_length=128, blank=True)
    # Financial dimensions (F9) — a {dimension_code: value_code} map for analytical slicing. Additive
    # + backward-compatible: legacy lines default {} (no dimensions), so nothing changes for them.
    dimensions = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "ledger_journal_lines"
        indexes = [
            models.Index(fields=["workspace_id", "entry"]),
            models.Index(fields=["workspace_id", "account"]),
        ]

    def __str__(self):
        return f"{self.account_id} D{self.debit} C{self.credit}"


class PostingRule(TenantModel):
    """Maps a business event type to a journal template so modules post consistently WITHOUT
    bespoke code. ``template`` is a list of line specs::

        [{"account_code": "1300", "side": "debit",  "amount_field": "amount"},
         {"account_code": "2100", "side": "credit", "amount_field": "amount"}]

    ``amount_field`` reads a Decimal from the event context; ``fixed_amount`` is a literal.
    The bus validates the resulting entry balances like any other.
    """

    event_type = models.CharField(max_length=100)        # "inventory.received", "payroll.run.posted"
    name = models.CharField(max_length=150, blank=True)
    template = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "ledger_posting_rules"
        unique_together = [("workspace_id", "event_type")]
        indexes = [models.Index(fields=["workspace_id", "event_type"])]

    def __str__(self):
        return f"{self.event_type} → {len(self.template or [])} lines"


class AccountingSettings(TenantModel):
    """Per-workspace default account mappings (business-meaning → chart code). Finance modules
    resolve the account they post to through these settings instead of hardcoding codes, so an
    admin can re-point any posting to a different account without code changes (P2.15 Blocker 2).
    One row per workspace; seeded from ``seeding.ACCOUNT_DEFAULTS`` on provisioning."""

    default_cash_account = models.CharField(max_length=32, default="1000")
    default_receivable_account = models.CharField(max_length=32, default="1100")
    default_inventory_account = models.CharField(max_length=32, default="1200")
    default_finished_goods_account = models.CharField(max_length=32, default="1400")
    default_fixed_asset_account = models.CharField(max_length=32, default="1500")
    default_accumulated_depreciation_account = models.CharField(max_length=32, default="1600")
    default_wip_account = models.CharField(max_length=32, default="1700")
    default_payable_account = models.CharField(max_length=32, default="2000")
    default_grni_account = models.CharField(max_length=32, default="2050")
    default_revenue_account = models.CharField(max_length=32, default="4000")
    default_cogs_account = models.CharField(max_length=32, default="5000")
    default_depreciation_expense_account = models.CharField(max_length=32, default="6300")
    # Credit engine (F3) mappings.
    default_discount_account = models.CharField(max_length=32, default="4200")
    default_scholarship_account = models.CharField(max_length=32, default="6700")
    default_writeoff_account = models.CharField(max_length=32, default="6800")
    default_refund_account = models.CharField(max_length=32, default="4100")
    # Collections engine (F2) mappings.
    default_late_fee_income_account = models.CharField(max_length=32, default="4900")
    # Tax engine (G1) mappings — output tax liability (collected), input tax recoverable (paid).
    default_output_tax_account = models.CharField(max_length=32, default="2210")
    default_input_tax_account = models.CharField(max_length=32, default="1450")
    # Multi-currency mappings — realized + unrealized FX gain / loss.
    default_fx_gain_account = models.CharField(max_length=32, default="4930")
    default_fx_loss_account = models.CharField(max_length=32, default="6960")
    # Multi-company / consolidation (F11) — intercompany control + CTA reserve.
    default_ic_receivable_account = models.CharField(max_length=32, default="1900")
    default_ic_payable_account = models.CharField(max_length=32, default="2900")
    default_cta_account = models.CharField(max_length=32, default="3900")
    # Treasury (F12) — investments placed, borrowings drawn, interest earned / paid.
    default_investment_account = models.CharField(max_length=32, default="1250")
    default_borrowing_account = models.CharField(max_length=32, default="2600")
    default_interest_income_account = models.CharField(max_length=32, default="4920")
    default_interest_expense_account = models.CharField(max_length=32, default="6500")
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "ledger_accounting_settings"
        unique_together = [("workspace_id",)]
        indexes = [models.Index(fields=["workspace_id"])]

    def __str__(self):
        return f"AccountingSettings({self.workspace_id})"
