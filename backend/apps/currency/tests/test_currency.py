"""
Multi-Currency + FX certification (Financial Platform).

Proves: the currency master + effective-dated exchange rates + conversion; that a FOREIGN-currency and
a MIXED-currency journal entry balance in the BASE currency and that account balances/statements report
in base; realized FX helper; unrealized FX REVALUATION posting; and — critically — that a workspace
with NO currency master behaves EXACTLY as before (single-currency backward compatibility).
"""
import datetime as dt
import uuid
from decimal import Decimal

import pytest

from apps.currency.fx import FxService
from apps.currency.services import CurrencyError, CurrencyService
from apps.ledger.models import LedgerAccount
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus


def _d(v):
    return Decimal(str(v))


def _bal(ws, code):
    return GLBus.account_balance(ws, LedgerAccount.objects.get(workspace_id=ws, code=code).id)


def _setup(ws, *, base="USD"):
    provision_accounting(ws)
    CurrencyService.set_base(workspace_id=ws, code=base)


# ── currency master + conversion ────────────────────────────────────────────────
@pytest.mark.django_db
def test_conversion_uses_effective_dated_rate():
    ws = uuid.uuid4()
    _setup(ws)
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.10",
                             effective_date=dt.date(2026, 1, 1))
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.20",
                             effective_date=dt.date(2026, 6, 1))
    assert CurrencyService.convert(ws, "100", "EUR", "USD", on_date=dt.date(2026, 3, 1)) == \
        _d("110.00")
    assert CurrencyService.convert(ws, "100", "EUR", "USD", on_date=dt.date(2026, 7, 1)) == \
        _d("120.00")


@pytest.mark.django_db
def test_inverse_rate_is_derived():
    ws = uuid.uuid4()
    _setup(ws)
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.25")
    # USD->EUR is derived as 1/1.25 = 0.8
    assert CurrencyService.convert(ws, "100", "USD", "EUR") == _d("80.00")


@pytest.mark.django_db
def test_missing_rate_raises():
    ws = uuid.uuid4()
    _setup(ws)
    with pytest.raises(CurrencyError):
        CurrencyService.convert(ws, "100", "EUR", "USD")


# ── backward compatibility (no currency master) ─────────────────────────────────
@pytest.mark.django_db
def test_single_currency_posting_unchanged_without_master():
    """A workspace with NO currency master posts exactly as before: base == transaction, balance
    checked on transaction amounts."""
    ws = uuid.uuid4()
    provision_accounting(ws)                       # NB: no base currency configured
    GLBus.post(ws, date=dt.date(2026, 1, 1), lines=[
        {"account_code": "1100", "debit": "100"},
        {"account_code": "4000", "credit": "100"}], source_ref="s1")
    assert _bal(ws, "1100") == _d("100.00")        # base == txn
    assert _bal(ws, "4000") == _d("-100.00")


# ── foreign + mixed currency entries ────────────────────────────────────────────
@pytest.mark.django_db
def test_foreign_currency_entry_balances_in_base():
    ws = uuid.uuid4()
    _setup(ws)
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.10")
    # a EUR sale: both lines in EUR → balances in EUR AND base (USD)
    GLBus.post(ws, date=dt.date(2026, 1, 1), lines=[
        {"account_code": "1100", "debit": "100", "currency": "EUR"},
        {"account_code": "4000", "credit": "100", "currency": "EUR"}], source_ref="eur-1")
    # base balance = 100 EUR × 1.10 = 110 USD
    assert _bal(ws, "1100") == _d("110.00")
    assert _bal(ws, "4000") == _d("-110.00")


@pytest.mark.django_db
def test_mixed_currency_entry_balances_on_base():
    """A payment received in EUR settling a USD receivable — a MIXED entry that balances only in base
    (100 USD debit-side vs 90.91 EUR credit-side ≈ 100 USD)."""
    ws = uuid.uuid4()
    _setup(ws)
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.10")
    # Dr Cash 90.91 EUR (=100.00 USD) / Cr A/R 100 USD  → balances in base
    GLBus.post(ws, date=dt.date(2026, 1, 1), lines=[
        {"account_code": "1000", "debit": "90.91", "currency": "EUR"},
        {"account_code": "1100", "credit": "100", "currency": "USD"}], source_ref="mix-1")
    assert _bal(ws, "1000") == _d("100.00")        # 90.91 EUR × 1.10 = 100.00 USD base
    assert _bal(ws, "1100") == _d("-100.00")


@pytest.mark.django_db
def test_unbalanced_mixed_entry_rejected():
    ws = uuid.uuid4()
    _setup(ws)
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.10")
    from apps.ledger.services import LedgerError
    with pytest.raises(LedgerError):
        GLBus.post(ws, date=dt.date(2026, 1, 1), lines=[
            {"account_code": "1000", "debit": "100", "currency": "EUR"},   # =110 USD
            {"account_code": "1100", "credit": "100", "currency": "USD"}],  # =100 USD → unbalanced
            source_ref="bad-1")


# ── FX gain/loss ────────────────────────────────────────────────────────────────
def test_realized_gain_loss_helper():
    assert FxService.realized_gain_loss(booked_base="100", settled_base="110")["is_gain"] is True
    assert FxService.realized_gain_loss(booked_base="100", settled_base="110")["amount"] == "10.00"
    assert FxService.realized_gain_loss(booked_base="100", settled_base="95")["is_gain"] is False


@pytest.mark.django_db
def test_unrealized_revaluation_posts_fx_adjustment():
    """Revalue an open EUR receivable to a higher closing rate → post an unrealized FX gain."""
    ws = uuid.uuid4()
    _setup(ws)
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.10")
    # book a 100 EUR receivable at 1.10 → base 110
    GLBus.post(ws, date=dt.date(2026, 1, 1), lines=[
        {"account_code": "1100", "debit": "100", "currency": "EUR"},
        {"account_code": "4000", "credit": "100", "currency": "EUR"}], source_ref="eur-open")
    assert _bal(ws, "1100") == _d("110.00")
    # closing rate 1.20 → target base = 120 → +10 unrealized gain
    out = FxService.revalue_account(workspace_id=ws, account_code="1100", currency="EUR",
                                    closing_rate="1.20", as_of=dt.date(2026, 1, 31))
    assert out["revalued"] is True and out["adjustment"] == "10.00"
    assert _bal(ws, "1100") == _d("120.00")        # AR now carried at closing rate
    assert _bal(ws, "4930") == _d("-10.00")        # FX gain (revenue, credit)
    # re-running at the same rate is convergent (no further posting)
    again = FxService.revalue_account(workspace_id=ws, account_code="1100", currency="EUR",
                                      closing_rate="1.20", as_of=dt.date(2026, 1, 31))
    assert again["revalued"] is False


@pytest.mark.django_db
def test_reversal_preserves_base_amounts():
    ws = uuid.uuid4()
    _setup(ws)
    CurrencyService.set_rate(workspace_id=ws, from_currency="EUR", to_currency="USD", rate="1.10")
    entry = GLBus.post(ws, date=dt.date(2026, 1, 1), lines=[
        {"account_code": "1100", "debit": "100", "currency": "EUR"},
        {"account_code": "4000", "credit": "100", "currency": "EUR"}], source_ref="rev-eur")
    GLBus.reverse(ws, entry.id)
    assert _bal(ws, "1100") == _d("0.00")          # reversal nets base to zero
    assert _bal(ws, "4000") == _d("0.00")


@pytest.mark.django_db
def test_currency_workspace_isolation_and_capability():
    from apps.packaging.capabilities import capability_available
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    CurrencyService.set_base(workspace_id=ws_a, code="USD")
    assert CurrencyService.base_code(ws_a) == "USD"
    assert CurrencyService.base_code(ws_b) == ""   # isolated
    assert capability_available("multi_currency") and capability_available("fx_revaluation")
