"""
Cash Management & Bank Reconciliation (F8) certification.

Proves the reusable engine: bank/cash accounts over GL, transfers posting ONE GL entry (no duplicate
accounting), cash instruments (cheque/deposit/EFT via instrument_type), cash position, statement
import, and DETERMINISTIC matching — exact/reference/tolerance (auto 1:1) + manual split/partial/
one-to-many — with duplicate prevention, plus a balanced reconciliation and outstanding items. GL stays
the single owner (reconciliation references JournalLine ids, posts nothing).
"""
import datetime as dt
import uuid
from decimal import Decimal

import pytest

from apps.cash.models import (
    BankReconciliation,
    BankStatementLine,
    CashInstrument,
    ReconciliationMatch,
)
from apps.cash.services import (
    CashError,
    CashService,
    MatchingService,
    ReconciliationService,
)
from apps.ledger.models import JournalEntry, LedgerAccount
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus


def _d(v):
    return Decimal(str(v))


def _bal(ws, code):
    return GLBus.account_balance(ws, LedgerAccount.objects.get(workspace_id=ws, code=code).id)


def _accounts(ws):
    provision_accounting(ws)
    a = CashService.ensure_account(workspace_id=ws, code="MAIN", name="Main Bank",
                                   account_type="bank", gl_account_code="1010")
    b = CashService.ensure_account(workspace_id=ws, code="PETTY", name="Petty Cash",
                                   account_type="cash", gl_account_code="1000")
    return a, b


def _deposit(ws, amount, *, date, ref="", memo=""):
    """A customer receipt into the main bank: Dr Bank(1010) / Cr A/R(1100)."""
    return GLBus.post(ws, date=date, lines=[
        {"account_code": "1010", "debit": str(amount), "memo": memo, "partner_ref": ref},
        {"account_code": "1100", "credit": str(amount)}],
        source_module="test", source_ref=f"dep-{amount}-{ref}")


# ── accounts + transfers (GL ownership) ─────────────────────────────────────────
@pytest.mark.django_db
def test_transfer_posts_one_gl_entry_no_duplication():
    ws = uuid.uuid4()
    main, petty = _accounts(ws)
    # fund the bank first
    _deposit(ws, 1000, date=dt.date(2026, 1, 1))
    xfer = CashService.post_transfer(workspace_id=ws, from_account=main.id, to_account=petty.id,
                                     amount="200", transfer_date=dt.date(2026, 1, 2),
                                     external_ref="t1")
    assert xfer.journal_entry_id is not None and xfer.transfer_type == "bank_to_cash"
    assert _bal(ws, "1010") == _d("800.00")       # bank down 200
    assert _bal(ws, "1000") == _d("200.00")       # cash up 200
    # exactly ONE GL entry for the transfer (no duplicate accounting)
    assert JournalEntry.objects.filter(workspace_id=ws, source_module="cash",
                                       source_ref=xfer.number).count() == 1


@pytest.mark.django_db
def test_transfer_is_idempotent_and_rejects_same_account():
    ws = uuid.uuid4()
    main, petty = _accounts(ws)
    _deposit(ws, 500, date=dt.date(2026, 1, 1))
    for _ in range(2):
        CashService.post_transfer(workspace_id=ws, from_account=main.id, to_account=petty.id,
                                  amount="100", external_ref="dup")
    from apps.cash.models import BankTransfer
    assert BankTransfer.objects.filter(workspace_id=ws, external_ref="dup").count() == 1
    with pytest.raises(CashError):
        CashService.post_transfer(workspace_id=ws, from_account=main.id, to_account=main.id,
                                  amount="10")


@pytest.mark.django_db
def test_cash_position_sums_book_balances():
    ws = uuid.uuid4()
    _accounts(ws)
    _deposit(ws, 1000, date=dt.date(2026, 1, 1))
    pos = CashService.cash_position(ws)
    assert pos["total_available"] == "1000.00"
    assert {r["code"] for r in pos["accounts"]} == {"MAIN", "PETTY"}


@pytest.mark.django_db
def test_cash_instrument_generalizes_cheque_deposit_eft():
    ws = uuid.uuid4()
    main, _ = _accounts(ws)
    inst = CashService.record_instrument(workspace_id=ws, bank_account=main.id, amount="300",
                                         instrument_type="cheque_received", reference="CHQ-99")
    assert inst.status == CashInstrument.PENDING
    CashService.set_instrument_status(workspace_id=ws, instrument_id=inst.id, status="cleared",
                                      clearing_date=dt.date(2026, 1, 10))
    assert CashInstrument.objects.get(id=inst.id).status == "cleared"


# ── deterministic matching + reconciliation ─────────────────────────────────────
def _recon_with_statement(ws, main, stmt_lines, *, closing):
    stmt = ReconciliationService.import_statement(
        workspace_id=ws, bank_account=main.id, lines=stmt_lines,
        statement_ref="ST1", statement_date=dt.date(2026, 1, 31), closing_balance=closing,
        external_ref="st1")
    return ReconciliationService.open_reconciliation(
        workspace_id=ws, bank_account=main.id, statement=stmt.id)


@pytest.mark.django_db
def test_auto_match_exact_and_reference():
    ws = uuid.uuid4()
    main, _ = _accounts(ws)
    _deposit(ws, 500, date=dt.date(2026, 1, 5), ref="INV-1")     # book line, ref INV-1
    _deposit(ws, 250, date=dt.date(2026, 1, 6))                  # book line, no ref
    rec = _recon_with_statement(ws, main, [
        {"line_date": dt.date(2026, 1, 5), "amount": "500", "direction": "in", "reference": "INV-1"},
        {"line_date": dt.date(2026, 1, 6), "amount": "250", "direction": "in"},
    ], closing="750")
    out = MatchingService.auto_match(workspace_id=ws, reconciliation_id=rec.id)
    assert out["matched"] == 2 and out["reference"] == 1 and out["exact"] == 1
    assert not rec.statement.lines.filter(status=BankStatementLine.UNMATCHED).exists()
    rec.refresh_from_db()
    assert rec.difference == _d("0.00")                          # fully reconciled


@pytest.mark.django_db
def test_auto_match_tolerance():
    ws = uuid.uuid4()
    main, _ = _accounts(ws)
    _deposit(ws, 100, date=dt.date(2026, 1, 5))
    rec = _recon_with_statement(ws, main, [
        {"line_date": dt.date(2026, 1, 5), "amount": "100.02", "direction": "in"},  # 2c bank fee diff
    ], closing="100.02")
    # no match without tolerance
    assert MatchingService.auto_match(workspace_id=ws, reconciliation_id=rec.id)["matched"] == 0
    # matched within a 5c tolerance
    out = MatchingService.auto_match(workspace_id=ws, reconciliation_id=rec.id,
                                     amount_tolerance="0.05")
    assert out["tolerance"] == 1


@pytest.mark.django_db
def test_reconciliation_reports_outstanding_items():
    ws = uuid.uuid4()
    main, _ = _accounts(ws)
    _deposit(ws, 500, date=dt.date(2026, 1, 5))                  # in books
    _deposit(ws, 300, date=dt.date(2026, 1, 30))                # deposit in transit (not on stmt)
    rec = _recon_with_statement(ws, main, [
        {"line_date": dt.date(2026, 1, 5), "amount": "500", "direction": "in"},
        {"line_date": dt.date(2026, 1, 20), "amount": "10", "direction": "out",
         "reference": "bank-fee"},                               # bank-only item (not in books)
    ], closing="490")   # 500 matched − 10 fee = 490 on the bank
    MatchingService.auto_match(workspace_id=ws, reconciliation_id=rec.id)
    items = ReconciliationService.outstanding_items(ws, rec)
    assert len(items["outstanding_book"]) == 1                   # the 300 deposit in transit
    assert len(items["outstanding_statement"]) == 1             # the 10 bank fee
    rec.refresh_from_db()
    assert rec.difference == _d("0.00")                          # difference fully explained
    done = ReconciliationService.complete(workspace_id=ws, reconciliation_id=rec.id)
    assert done.status == BankReconciliation.RECONCILED


@pytest.mark.django_db
def test_manual_split_match_and_duplicate_prevention():
    ws = uuid.uuid4()
    main, _ = _accounts(ws)
    b1 = _deposit(ws, 60, date=dt.date(2026, 1, 5))
    b2 = _deposit(ws, 40, date=dt.date(2026, 1, 5))
    # one statement line of 100 = the two book lines split
    rec = _recon_with_statement(ws, main, [
        {"line_date": dt.date(2026, 1, 5), "amount": "100", "direction": "in"}], closing="100")
    line = rec.statement.lines.first()
    bl1 = b1.lines.get(account__code="1010")
    bl2 = b2.lines.get(account__code="1010")
    out = MatchingService.match_group(workspace_id=ws, reconciliation_id=rec.id,
                                      statement_line_ids=[str(line.id)],
                                      journal_line_ids=[str(bl1.id), str(bl2.id)])
    assert out["matched"] is True and out["journal_lines"] == 2
    # duplicate prevention: matching the same book line again is rejected
    with pytest.raises(CashError):
        MatchingService.match_group(workspace_id=ws, reconciliation_id=rec.id,
                                    statement_line_ids=[str(line.id)],
                                    journal_line_ids=[str(bl1.id)])


@pytest.mark.django_db
def test_unmatch_restores_state():
    ws = uuid.uuid4()
    main, _ = _accounts(ws)
    _deposit(ws, 500, date=dt.date(2026, 1, 5), ref="INV-1")
    rec = _recon_with_statement(ws, main, [
        {"line_date": dt.date(2026, 1, 5), "amount": "500", "direction": "in", "reference": "INV-1"}],
        closing="500")
    MatchingService.auto_match(workspace_id=ws, reconciliation_id=rec.id)
    match = ReconciliationMatch.objects.get(workspace_id=ws, reconciliation=rec)
    MatchingService.unmatch(workspace_id=ws, match_id=match.id)
    assert rec.statement.lines.filter(status=BankStatementLine.UNMATCHED).count() == 1


# ── governance ──────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_statement_import_idempotent_and_isolated():
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    a, _ = _accounts(ws_a)
    for _ in range(2):
        ReconciliationService.import_statement(workspace_id=ws_a, bank_account=a.id,
                                               lines=[{"amount": "10", "direction": "in"}],
                                               external_ref="s")
    from apps.cash.models import BankStatement
    assert BankStatement.objects.filter(workspace_id=ws_a, external_ref="s").count() == 1
    assert not BankStatement.objects.filter(workspace_id=ws_b).exists()


def test_cash_registered_as_capabilities_and_actions():
    from apps.packaging.capabilities import capability_available
    from apps.workflows.executors import REGISTRY
    assert capability_available("cash_management") and capability_available("bank_reconciliation")
    for action in ["action_bank_transfer", "action_auto_reconcile"]:
        assert action in REGISTRY
