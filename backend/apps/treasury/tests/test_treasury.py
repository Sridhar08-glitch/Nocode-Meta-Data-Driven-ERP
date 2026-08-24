"""
Treasury Platform (F12) certification.

Proves the reusable engine: borrowings (``TreasuryFacility``) + investments (``TreasuryInvestment``)
as ``*_type`` metadata; every treasury EVENT as ONE ``TreasuryTransaction(transaction_type)`` that
posts through ``GLBus`` (no parallel accounting — every event carries a ``journal_entry_id`` and the
GL stays balanced); interest / debt / maturity SCHEDULES + liquidity + exposure + forecast as COMPUTED
reports (no stored duplication). Deterministic interest maths (no AI). Tenant-isolated; idempotent.
"""
import datetime as dt
import uuid
from decimal import Decimal

import pytest

from apps.cash.services import CashService
from apps.ledger.models import JournalEntry, LedgerAccount
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus
from apps.treasury.models import (
    TreasuryCounterparty,
    TreasuryFacility,
    TreasuryInvestment,
    TreasuryTransaction,
)
from apps.treasury.services import (
    InterestService,
    LiquidityService,
    ScheduleService,
    TreasuryError,
    TreasuryForecastService,
    TreasuryService,
)

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 1, 1)
MAT = dt.date(2026, 12, 31)


def _d(v):
    return Decimal(str(v))


def _bal(ws, code):
    return GLBus.account_balance(ws, LedgerAccount.objects.get(workspace_id=ws, code=code).id)


def _ws():
    ws = uuid.uuid4()
    provision_accounting(ws)
    return ws


def _counterparty(ws, code="BANK1"):
    return TreasuryCounterparty.objects.create(
        workspace_id=ws, code=code, name="Test Bank", counterparty_type="bank",
        exposure_limit=_d("1000000"))


# ── generalization: ONE facility model, facility_type metadata ────────────────────
def test_facility_types_are_metadata_not_tables():
    ws = _ws()
    for ftype in ("loan", "overdraft", "credit_facility", "bridge_loan"):
        f = TreasuryService.create_facility(
            workspace_id=ws, principal="100000", facility_type=ftype, currency="USD",
            interest_rate="6", start_date=TODAY, maturity_date=MAT)
        assert f.facility_type == ftype
    assert TreasuryFacility.objects.filter(workspace_id=ws).count() == 4


def test_investment_types_are_metadata():
    ws = _ws()
    for itype in ("deposit", "treasury_bill", "bond", "fund"):
        TreasuryService.create_investment(
            workspace_id=ws, principal="50000", investment_type=itype, currency="USD",
            interest_rate="4", start_date=TODAY, maturity_date=MAT)
    assert TreasuryInvestment.objects.filter(workspace_id=ws).count() == 4


# ── drawdown posts through GLBus (no parallel accounting) ─────────────────────────
def test_drawdown_posts_borrowing_to_gl():
    ws = _ws()
    f = TreasuryService.create_facility(
        workspace_id=ws, principal="100000", currency="USD", interest_rate="6",
        start_date=TODAY, maturity_date=MAT)
    txn = TreasuryService.drawdown(workspace_id=ws, facility_id=f.id)
    assert txn.transaction_type == TreasuryTransaction.DRAWDOWN
    assert txn.journal_entry_id is not None                 # posted via GLBus
    assert _bal(ws, "1010") == _d("100000")                 # Dr Cash
    assert _bal(ws, "2600") == _d("-100000")                # Cr Borrowings
    f.refresh_from_db()
    assert f.outstanding == _d("100000")
    assert f.drawn_amount == _d("100000")


def test_place_investment_posts_to_gl():
    ws = _ws()
    inv = TreasuryService.create_investment(
        workspace_id=ws, principal="60000", currency="USD", interest_rate="4",
        start_date=TODAY, maturity_date=MAT)
    txn = TreasuryService.place_investment(workspace_id=ws, investment_id=inv.id)
    assert txn.transaction_type == TreasuryTransaction.INVESTMENT_PURCHASE
    assert txn.journal_entry_id is not None
    assert _bal(ws, "1250") == _d("60000")                  # Dr Investment
    assert _bal(ws, "1010") == _d("-60000")                 # Cr Cash


# ── repay + mature lifecycle ──────────────────────────────────────────────────────
def test_repay_principal_closes_facility():
    ws = _ws()
    f = TreasuryService.create_facility(
        workspace_id=ws, principal="80000", currency="USD", interest_rate="5",
        start_date=TODAY, maturity_date=MAT)
    TreasuryService.drawdown(workspace_id=ws, facility_id=f.id)
    TreasuryService.repay_principal(workspace_id=ws, facility_id=f.id, amount="30000", date=MAT)
    f.refresh_from_db()
    assert f.outstanding == _d("50000")
    assert f.status == TreasuryFacility.ACTIVE
    TreasuryService.repay_principal(workspace_id=ws, facility_id=f.id, date=MAT)   # full remainder
    f.refresh_from_db()
    assert f.outstanding == _d("0")
    assert f.status == TreasuryFacility.REPAID
    assert _bal(ws, "2600") == _d("0")                      # borrowing fully cleared


def test_mature_investment():
    ws = _ws()
    inv = TreasuryService.create_investment(
        workspace_id=ws, principal="60000", currency="USD", interest_rate="4",
        start_date=TODAY, maturity_date=MAT)
    TreasuryService.place_investment(workspace_id=ws, investment_id=inv.id)
    txn = TreasuryService.mature_investment(workspace_id=ws, investment_id=inv.id, date=MAT)
    assert txn.transaction_type == TreasuryTransaction.MATURITY
    inv.refresh_from_db()
    assert inv.status == TreasuryInvestment.MATURED
    assert inv.outstanding == _d("0")
    assert _bal(ws, "1250") == _d("0")                      # investment redeemed to cash


# ── interest run posts + is idempotent ────────────────────────────────────────────
def test_pay_interest_due_posts_expense_and_income_idempotently():
    ws = _ws()
    fac = TreasuryService.create_facility(
        workspace_id=ws, principal="120000", currency="USD", interest_rate="12",
        payment_frequency="quarterly", start_date=TODAY, maturity_date=MAT)
    TreasuryService.drawdown(workspace_id=ws, facility_id=fac.id)
    inv = TreasuryService.create_investment(
        workspace_id=ws, principal="100000", currency="USD", interest_rate="8",
        payment_frequency="quarterly", start_date=TODAY, maturity_date=MAT)
    TreasuryService.place_investment(workspace_id=ws, investment_id=inv.id)

    horizon = dt.date(2027, 1, 31)                         # capture all 4 quarterly coupons
    first = TreasuryService.pay_interest_due(workspace_id=ws, as_of=horizon)
    assert first["posted"] == 8                             # 4 facility + 4 investment periods
    exp1 = _bal(ws, "6500")
    inc1 = _bal(ws, "4920")
    assert exp1 > 0 and inc1 < 0                            # interest expense Dr, income Cr

    # Re-run: every (deal, period) already posted → nothing new, GL unchanged (idempotent).
    second = TreasuryService.pay_interest_due(workspace_id=ws, as_of=horizon)
    assert second["posted"] == 0
    assert _bal(ws, "6500") == exp1
    assert _bal(ws, "4920") == inc1
    # one journal per interest txn — no duplicates
    assert TreasuryTransaction.objects.filter(
        workspace_id=ws, transaction_type=TreasuryTransaction.INTEREST_PAYMENT).count() == 4


# ── computed schedules (not stored rows) ──────────────────────────────────────────
def test_interest_schedule_is_computed():
    ws = _ws()
    f = TreasuryService.create_facility(
        workspace_id=ws, principal="120000", currency="USD", interest_rate="12",
        payment_frequency="quarterly", start_date=TODAY, maturity_date=MAT)
    rows = ScheduleService.interest_schedule(ws, "facility", f.id)
    assert len(rows) == 4                                   # quarterly over ~1yr
    assert all(Decimal(r["interest"]) > 0 for r in rows)
    assert [r["period_no"] for r in rows] == [1, 2, 3, 4]


def test_bullet_schedule_single_period():
    ws = _ws()
    f = TreasuryService.create_facility(
        workspace_id=ws, principal="100000", currency="USD", interest_rate="10",
        payment_frequency="bullet", start_date=TODAY, maturity_date=MAT)
    rows = ScheduleService.interest_schedule(ws, "facility", f.id)
    assert len(rows) == 1


def test_debt_and_maturity_schedules():
    ws = _ws()
    f = TreasuryService.create_facility(
        workspace_id=ws, principal="100000", currency="USD", interest_rate="6",
        start_date=TODAY, maturity_date=MAT)
    TreasuryService.drawdown(workspace_id=ws, facility_id=f.id)
    inv = TreasuryService.create_investment(
        workspace_id=ws, principal="50000", currency="USD", interest_rate="4",
        start_date=TODAY, maturity_date=dt.date(2026, 6, 30))
    TreasuryService.place_investment(workspace_id=ws, investment_id=inv.id)

    debt = ScheduleService.debt_schedule(ws)
    assert len(debt) == 1 and debt[0]["outstanding"] == "100000.00"
    mat = ScheduleService.maturity_schedule(ws)
    assert [r["kind"] for r in mat] == ["investment", "facility"]   # sorted by maturity date


# ── liquidity / exposure / forecast (computed, reuse cash) ────────────────────────
def test_liquidity_position_combines_cash_investments_borrowings():
    ws = _ws()
    # cash: a funded bank account (reuse F8)
    acct = CashService.ensure_account(workspace_id=ws, code="MAIN", name="Main",
                                      account_type="bank", gl_account_code="1010")
    GLBus.post(ws, date=TODAY, lines=[{"account_code": "1010", "debit": "200000"},
                                      {"account_code": "3000", "credit": "200000"}],
               source_module="test", source_ref="seed-cash")
    f = TreasuryService.create_facility(
        workspace_id=ws, principal="100000", currency="USD", interest_rate="6",
        start_date=TODAY, maturity_date=MAT)
    TreasuryService.drawdown(workspace_id=ws, facility_id=f.id)     # +100k cash, +100k borrowing
    inv = TreasuryService.create_investment(
        workspace_id=ws, principal="50000", currency="USD", interest_rate="4",
        start_date=TODAY, maturity_date=MAT)
    TreasuryService.place_investment(workspace_id=ws, investment_id=inv.id)   # -50k cash, +50k inv

    pos = LiquidityService.position(ws)
    assert pos["investments"] == "50000.00"
    assert pos["borrowings"] == "100000.00"
    # cash = 200k + 100k drawdown - 50k placement = 250k; net = 250k + 50k - 100k = 200k
    assert pos["cash"] == "250000.00"
    assert pos["net_liquidity"] == "200000.00"
    assert acct.code == "MAIN"


def test_counterparty_exposure():
    ws = _ws()
    cp = _counterparty(ws)
    inv = TreasuryService.create_investment(
        workspace_id=ws, principal="75000", currency="USD", interest_rate="4",
        counterparty_id=cp.id, start_date=TODAY, maturity_date=MAT)
    TreasuryService.place_investment(workspace_id=ws, investment_id=inv.id)
    rows = LiquidityService.counterparty_exposure(ws)
    assert rows == [{"counterparty": "BANK1", "limit": "1000000.00", "exposure": "75000.00"}]


def test_forecast_projects_interest_and_maturities():
    ws = _ws()
    inv = TreasuryService.create_investment(
        workspace_id=ws, principal="100000", currency="USD", interest_rate="8",
        payment_frequency="quarterly", start_date=TODAY, maturity_date=MAT)
    TreasuryService.place_investment(workspace_id=ws, investment_id=inv.id)
    fc = TreasuryForecastService.forecast(ws, from_date=TODAY, to_date=dt.date(2027, 12, 31))
    assert Decimal(fc["projected_inflows"]) > 0            # coupons + maturity principal
    assert Decimal(fc["closing_liquidity"]) == (
        Decimal(fc["opening_liquidity"]) + Decimal(fc["net_projected"]))


# ── deterministic interest maths (no AI) ──────────────────────────────────────────
def test_interest_service_maths():
    assert InterestService.simple_interest(
        principal="100000", annual_rate_pct="12", days=90, day_count=360) == _d("3000.00")
    # 10% compounded monthly for 1yr ≈ 10.4713% effective
    eff = InterestService.effective_rate(nominal_pct="10", periods_per_year=12)
    assert Decimal("10.47") < eff < Decimal("10.48")
    assert InterestService.floating_rate(reference_rate_pct="5", spread_pct="1.5") == _d("6.5")
    ci = InterestService.compound_interest(
        principal="100000", annual_rate_pct="10", years=1, periods_per_year=12)
    assert Decimal("10400") < ci < Decimal("10500")


# ── accounting integrity: every txn balances + posts via GLBus ────────────────────
def test_every_event_balances_the_gl():
    ws = _ws()
    f = TreasuryService.create_facility(
        workspace_id=ws, principal="100000", currency="USD", interest_rate="6",
        payment_frequency="annual", start_date=TODAY, maturity_date=MAT)
    TreasuryService.drawdown(workspace_id=ws, facility_id=f.id)
    TreasuryService.pay_interest_due(workspace_id=ws, as_of=MAT)
    TreasuryService.repay_principal(workspace_id=ws, facility_id=f.id, date=MAT)
    # every treasury journal balances (debits == credits)
    for je in JournalEntry.objects.filter(workspace_id=ws, source_module="treasury"):
        d = sum((line.base_debit for line in je.lines.all()), Decimal("0"))
        c = sum((line.base_credit for line in je.lines.all()), Decimal("0"))
        assert d == c and d > 0
    # no treasury transaction exists without a GL entry (no parallel accounting)
    assert not TreasuryTransaction.objects.filter(
        workspace_id=ws, journal_entry_id__isnull=True).exists()


# ── tenant isolation ──────────────────────────────────────────────────────────────
def test_tenant_isolation():
    ws1, ws2 = _ws(), _ws()
    TreasuryService.create_facility(
        workspace_id=ws1, principal="100000", currency="USD", interest_rate="6",
        start_date=TODAY, maturity_date=MAT)
    assert TreasuryFacility.objects.filter(workspace_id=ws2).count() == 0
    assert TreasuryFacility.objects.filter(workspace_id=ws1).count() == 1


# ── validation ────────────────────────────────────────────────────────────────────
def test_negative_principal_rejected():
    ws = _ws()
    with pytest.raises(TreasuryError):
        TreasuryService.create_facility(
            workspace_id=ws, principal="-5", currency="USD", interest_rate="6")
    with pytest.raises(TreasuryError):
        TreasuryService.create_investment(
            workspace_id=ws, principal="0", currency="USD", interest_rate="4")


def test_missing_deal_rejected():
    ws = _ws()
    with pytest.raises(TreasuryError):
        TreasuryService.drawdown(workspace_id=ws, facility_id=uuid.uuid4())
    with pytest.raises(TreasuryError):
        TreasuryService.mature_investment(workspace_id=ws, investment_id=uuid.uuid4())
