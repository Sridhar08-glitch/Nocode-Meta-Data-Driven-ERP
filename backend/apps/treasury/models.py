"""
Treasury Platform (Financial Platform — F12) — the reusable Core capability for borrowings, investments,
interest, debt/repayment schedules, liquidity and treasury forecasting.

Treasury OWNS treasury (facilities/borrowings, investments, interest schedules, counterparties) and
REUSES everything else — GL posting (``GLBus``; no parallel accounting), Cash position (F8), Currency
(F7), Settlement AR/AP + Budgets (F10) for forecasting, Dimensions (F9) + company_id (F11) on postings.
Interest is deterministic (no AI). Generalization: a borrowing is a ``TreasuryFacility(facility_type)``;
an investment is a ``TreasuryInvestment(investment_type)``; every realized treasury EVENT (drawdown /
interest / principal / coupon / maturity / fee / FX) is ONE ``TreasuryTransaction(transaction_type)``.
Interest / maturity / debt / cashflow SCHEDULES, plus liquidity, forecast, position and exposure, are
COMPUTED reports (no stored duplication). Workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 20, "decimal_places": 2, "default": 0}
RATE = {"max_digits": 12, "decimal_places": 6, "default": 0}

RATE_TYPES = [("fixed", "Fixed"), ("floating", "Floating")]
COMPOUNDING = [("simple", "Simple"), ("compound", "Compound"), ("effective", "Effective")]


class TreasuryCounterparty(TenantModel):
    """A bank / lender / issuer / fund the entity deals with — enables counterparty exposure + limits."""

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=200)
    counterparty_type = models.CharField(max_length=16, default="bank", choices=[
        ("bank", "Bank"), ("government", "Government"), ("corporate", "Corporate"),
        ("fund", "Fund"), ("other", "Other")])
    credit_rating = models.CharField(max_length=16, blank=True)
    exposure_limit = models.DecimalField(**MONEY)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "treasury_counterparties"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "code"])]

    def __str__(self):
        return f"{self.code} {self.name}"


class _Deal(TenantModel):
    """Shared base for the two deal kinds (borrowings + investments) — identical structure, opposite
    direction/GL. Not a table itself."""

    number = models.CharField(max_length=64, blank=True)
    counterparty = models.ForeignKey(TreasuryCounterparty, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    principal = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, blank=True)
    rate_type = models.CharField(max_length=8, choices=RATE_TYPES, default="fixed")
    interest_rate = models.DecimalField(**RATE)                   # annual percent
    reference_rate = models.CharField(max_length=32, blank=True)  # floating benchmark (SOFR/EURIBOR)
    spread = models.DecimalField(**RATE)                          # floating margin
    compounding = models.CharField(max_length=10, choices=COMPOUNDING, default="simple")
    day_count = models.PositiveIntegerField(default=365)          # day-count basis
    payment_frequency = models.CharField(max_length=12, default="monthly", choices=[
        ("monthly", "Monthly"), ("quarterly", "Quarterly"), ("semi_annual", "Semi-Annual"),
        ("annual", "Annual"), ("bullet", "Bullet (at maturity)")])
    start_date = models.DateField(null=True, blank=True)
    maturity_date = models.DateField(null=True, blank=True)
    company_id = models.UUIDField(null=True, blank=True)          # F11 legal entity
    dimensions = models.JSONField(default=dict, blank=True)       # F9 analytical tags
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        abstract = True


class TreasuryFacility(_Deal):
    """A BORROWING — loan / overdraft / credit facility / line of credit / bridge / project finance
    (``facility_type`` metadata; no per-variant tables). We owe principal + pay interest."""

    ACTIVE = "active"
    REPAID = "repaid"
    CLOSED = "closed"
    STATUS_CHOICES = [(ACTIVE, "Active"), (REPAID, "Repaid"), (CLOSED, "Closed")]

    facility_type = models.CharField(max_length=20, default="loan", choices=[
        ("loan", "Loan"), ("overdraft", "Overdraft"), ("credit_facility", "Credit Facility"),
        ("line_of_credit", "Line of Credit"), ("bridge_loan", "Bridge Loan"),
        ("project_finance", "Project Finance")])
    facility_limit = models.DecimalField(**MONEY)                 # for revolving facilities
    drawn_amount = models.DecimalField(**MONEY)
    outstanding = models.DecimalField(**MONEY)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=ACTIVE)

    class Meta:
        db_table = "treasury_facilities"
        indexes = [models.Index(fields=["workspace_id", "facility_type", "status"]),
                   models.Index(fields=["workspace_id", "counterparty"])]

    def __str__(self):
        return f"{self.number} {self.facility_type} {self.principal}"


class TreasuryInvestment(_Deal):
    """An INVESTMENT — deposit / money-market / treasury-bill / bond / commercial-paper / fund
    (``investment_type`` metadata). We place principal + earn interest."""

    ACTIVE = "active"
    MATURED = "matured"
    REDEEMED = "redeemed"
    STATUS_CHOICES = [(ACTIVE, "Active"), (MATURED, "Matured"), (REDEEMED, "Redeemed")]

    investment_type = models.CharField(max_length=20, default="deposit", choices=[
        ("deposit", "Deposit"), ("money_market", "Money Market"), ("treasury_bill", "Treasury Bill"),
        ("bond", "Bond"), ("commercial_paper", "Commercial Paper"), ("fund", "Fund")])
    face_value = models.DecimalField(**MONEY)                     # for discount instruments (T-bills)
    outstanding = models.DecimalField(**MONEY)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=ACTIVE)

    class Meta:
        db_table = "treasury_investments"
        indexes = [models.Index(fields=["workspace_id", "investment_type", "status"]),
                   models.Index(fields=["workspace_id", "counterparty"])]

    def __str__(self):
        return f"{self.number} {self.investment_type} {self.principal}"


class TreasuryTransaction(TenantModel):
    """THE single transactional entity — every realized treasury EVENT (``transaction_type`` metadata:
    drawdown / interest accrual+payment / principal repayment / investment purchase+sale / coupon /
    dividend / maturity / fee / FX settlement). They share one structure + one lifecycle, so they are
    ONE entity, not separate tables (6/7-point; the diagnostic_order / prescription / FinancialPlan
    precedent). Interest / maturity / debt / cashflow SCHEDULES are COMPUTED reports, not stored rows.
    Each event posts through ``GLBus`` (``journal_entry_id``); ``facility``/``investment`` are optional
    (a deal-independent fee/FX has neither)."""

    DRAWDOWN = "drawdown"
    PRINCIPAL_REPAYMENT = "principal_repayment"
    INTEREST_ACCRUAL = "interest_accrual"
    INTEREST_PAYMENT = "interest_payment"
    INVESTMENT_PURCHASE = "investment_purchase"
    INVESTMENT_SALE = "investment_sale"
    COUPON = "coupon"
    DIVIDEND = "dividend"
    MATURITY = "maturity"
    FEE = "fee"
    FX_SETTLEMENT = "fx_settlement"
    TYPE_CHOICES = [
        (DRAWDOWN, "Drawdown"), (PRINCIPAL_REPAYMENT, "Principal Repayment"),
        (INTEREST_ACCRUAL, "Interest Accrual"), (INTEREST_PAYMENT, "Interest Payment"),
        (INVESTMENT_PURCHASE, "Investment Purchase"), (INVESTMENT_SALE, "Investment Sale"),
        (COUPON, "Coupon"), (DIVIDEND, "Dividend"), (MATURITY, "Maturity"), (FEE, "Fee"),
        (FX_SETTLEMENT, "FX Settlement")]

    POSTED = "posted"
    PENDING = "pending"
    REVERSED = "reversed"
    STATUS_CHOICES = [(POSTED, "Posted"), (PENDING, "Pending"), (REVERSED, "Reversed")]

    number = models.CharField(max_length=64, blank=True)
    transaction_type = models.CharField(max_length=24, choices=TYPE_CHOICES)
    facility = models.ForeignKey(TreasuryFacility, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name="transactions")
    investment = models.ForeignKey(TreasuryInvestment, null=True, blank=True,
                                   on_delete=models.CASCADE, related_name="transactions")
    counterparty = models.ForeignKey(TreasuryCounterparty, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="transactions")
    amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3, blank=True)
    value_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    company_id = models.UUIDField(null=True, blank=True)
    dimensions = models.JSONField(default=dict, blank=True)
    external_ref = models.CharField(max_length=160, blank=True, db_index=True)   # idempotency
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=POSTED)
    journal_entry_id = models.UUIDField(null=True, blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "treasury_transactions"
        indexes = [models.Index(fields=["workspace_id", "transaction_type", "status"]),
                   models.Index(fields=["workspace_id", "facility"]),
                   models.Index(fields=["workspace_id", "investment"]),
                   models.Index(fields=["workspace_id", "value_date"]),
                   models.Index(fields=["workspace_id", "external_ref"])]

    def __str__(self):
        return f"{self.transaction_type} {self.amount} {self.value_date}"
