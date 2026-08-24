"""
Financial Statements engine (F6 / Gaps G6 + G8) certification.

Proves the standard statements are correct PURE READS over the single GL: Trial Balance (balanced),
Balance Sheet (A = L + E), Profit & Loss (net income), Cash Flow (cash movement), General Ledger
detail, and AR/AP Aging (bucketed by partner). No new accounting — every figure derives from posted
JournalLines, so every package's postings appear automatically.
"""
import datetime as dt
import uuid
from decimal import Decimal

import pytest

from apps.financial_reports.services import StatementService
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus


def _d(v):
    return Decimal(str(v))


def _sale(ws, amount, *, date, partner="cust-1"):
    """A simple sale: Dr A/R (1100) / Cr Revenue (4000)."""
    GLBus.post(ws, date=date, lines=[
        {"account_code": "1100", "debit": str(amount), "partner_ref": partner},
        {"account_code": "4000", "credit": str(amount)}],
        source_module="test", source_ref=f"sale-{amount}-{partner}")


def _cash_receipt(ws, amount, *, date, partner="cust-1"):
    """Collect cash: Dr Cash (1000) / Cr A/R (1100)."""
    GLBus.post(ws, date=date, lines=[
        {"account_code": "1000", "debit": str(amount)},
        {"account_code": "1100", "credit": str(amount), "partner_ref": partner}],
        source_module="test", source_ref=f"rcpt-{amount}-{partner}")


def _expense(ws, amount, *, date):
    """Pay rent: Dr Rent (6100) / Cr Cash (1000)."""
    GLBus.post(ws, date=date, lines=[
        {"account_code": "6100", "debit": str(amount)},
        {"account_code": "1000", "credit": str(amount)}],
        source_module="test", source_ref=f"exp-{amount}")


@pytest.fixture
def ws_with_activity():
    ws = uuid.uuid4()
    provision_accounting(ws)
    _sale(ws, 1000, date=dt.date(2026, 1, 10))
    _cash_receipt(ws, 400, date=dt.date(2026, 1, 20))
    _expense(ws, 150, date=dt.date(2026, 1, 25))
    return ws


@pytest.mark.django_db
def test_trial_balance_is_balanced(ws_with_activity):
    tb = StatementService.trial_balance(ws_with_activity)
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]
    codes = {r["code"]: r for r in tb["rows"]}
    assert codes["1100"]["debit"] == "600.00"          # A/R: 1000 sale − 400 collected
    assert codes["4000"]["credit"] == "1000.00"        # revenue


@pytest.mark.django_db
def test_profit_and_loss_net_income(ws_with_activity):
    pnl = StatementService.profit_and_loss(ws_with_activity)
    assert pnl["total_revenue"] == "1000.00"
    assert pnl["total_expenses"] == "150.00"
    assert pnl["net_income"] == "850.00"


@pytest.mark.django_db
def test_balance_sheet_balances(ws_with_activity):
    bs = StatementService.balance_sheet(ws_with_activity)
    assert bs["balanced"] is True
    # assets = cash(400-150=250) + A/R(600) = 850; equity = current earnings 850
    assert bs["total_assets"] == "850.00"
    ni = [e for e in bs["equity"] if e["code"] == "NI"][0]
    assert ni["amount"] == "850.00"


@pytest.mark.django_db
def test_cash_flow_movement(ws_with_activity):
    cf = StatementService.cash_flow(ws_with_activity, from_date=dt.date(2026, 1, 1),
                                    to_date=dt.date(2026, 1, 31))
    assert cf["inflows"] == "400.00"                   # cash receipt
    assert cf["outflows"] == "150.00"                  # rent
    assert cf["net_change"] == "250.00"
    assert cf["closing_cash"] == "250.00"


@pytest.mark.django_db
def test_general_ledger_running_balance(ws_with_activity):
    gl = StatementService.general_ledger(ws_with_activity, account_code="1100")
    assert gl["closing_balance"] == "600.00"
    assert [r["balance"] for r in gl["rows"]] == ["1000.00", "600.00"]   # sale then receipt


@pytest.mark.django_db
def test_ar_aging_buckets_by_age():
    """Line-level aging: each open receivable line is bucketed by its own age. (Invoice↔payment
    matching is a future Settlement-engine concern — documented; not faked here.)"""
    ws = uuid.uuid4()
    provision_accounting(ws)
    _sale(ws, 500, date=dt.date(2026, 1, 1), partner="old")      # ~2.5 months old
    _sale(ws, 300, date=dt.date(2026, 3, 10), partner="new")     # a few days old
    aging = StatementService.ar_aging(ws, as_of=dt.date(2026, 3, 15))
    rows = {r["partner_ref"]: r for r in aging["rows"]}
    assert rows["old"]["total"] == "500.00" and rows["old"]["60+"] == "500.00"
    assert rows["new"]["total"] == "300.00" and rows["new"]["current"] == "300.00"
    assert aging["grand_total"] == "800.00"


@pytest.mark.django_db
def test_ap_aging_reads_positive(ws_with_activity):
    ws = ws_with_activity
    # a vendor bill: Dr Expense (6100) / Cr A/P (2000)
    GLBus.post(ws, date=dt.date(2026, 1, 5), lines=[
        {"account_code": "6100", "debit": "500"},
        {"account_code": "2000", "credit": "500", "partner_ref": "vend-1"}],
        source_module="test", source_ref="bill-1")
    aging = StatementService.ap_aging(ws, as_of=dt.date(2026, 1, 31))
    row = [r for r in aging["rows"] if r["partner_ref"] == "vend-1"][0]
    assert row["total"] == "500.00"                    # payable shown positive


@pytest.mark.django_db
def test_statements_are_workspace_isolated():
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    provision_accounting(ws_a)
    provision_accounting(ws_b)
    _sale(ws_a, 100, date=dt.date(2026, 1, 1))
    assert StatementService.profit_and_loss(ws_a)["total_revenue"] == "100.00"
    assert StatementService.profit_and_loss(ws_b)["total_revenue"] == "0.00"


def test_financial_statements_registered_as_capability():
    from apps.packaging.capabilities import capability_available
    assert capability_available("financial_statements")
