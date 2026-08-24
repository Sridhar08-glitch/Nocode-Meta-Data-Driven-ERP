"""
Settlement / Payment-Allocation engine certification.

Proves the reusable sub-ledger matching: register open items, allocate (full/partial/split), FIFO
auto-allocation, settled/partial status, over-allocation rejection, invoice-matched aging, unallocate,
the workflow actions, idempotency and workspace isolation. Allocation posts NO GL (the invoice/payment
already posted) — this is a matching layer that enables invoice-matched aging.
"""
import datetime as dt
import types
import uuid
from decimal import Decimal

import pytest

from apps.settlement.models import Allocation, SettlementDocument
from apps.settlement.services import SettlementError, SettlementService


def _inv(ws, amount, *, partner="cust-1", date=None, ref="INV"):
    return SettlementService.register_document(
        workspace_id=ws, partner_ref=partner, direction="debit", doc_type="invoice",
        amount=amount, document_ref=ref, document_date=date or dt.date(2026, 1, 1),
        external_ref=f"d:{partner}:{ref}:{amount}")


def _pay(ws, amount, *, partner="cust-1", date=None, ref="PAY"):
    return SettlementService.register_document(
        workspace_id=ws, partner_ref=partner, direction="credit", doc_type="payment",
        amount=amount, document_ref=ref, document_date=date or dt.date(2026, 1, 5),
        external_ref=f"c:{partner}:{ref}:{amount}")


@pytest.mark.django_db
def test_full_allocation_settles_both_documents():
    ws = uuid.uuid4()
    inv = _inv(ws, 100)
    pay = _pay(ws, 100)
    SettlementService.allocate(workspace_id=ws, credit_document_id=pay.id, debit_document_id=inv.id)
    inv.refresh_from_db()
    pay.refresh_from_db()
    assert inv.status == SettlementDocument.SETTLED and inv.outstanding == Decimal("0.00")
    assert pay.status == SettlementDocument.SETTLED


@pytest.mark.django_db
def test_partial_allocation_leaves_outstanding():
    ws = uuid.uuid4()
    inv = _inv(ws, 100)
    pay = _pay(ws, 40)
    SettlementService.allocate(workspace_id=ws, credit_document_id=pay.id, debit_document_id=inv.id)
    inv.refresh_from_db()
    assert inv.status == SettlementDocument.PARTIAL and inv.outstanding == Decimal("60.00")


@pytest.mark.django_db
def test_split_payment_across_two_invoices():
    ws = uuid.uuid4()
    a = _inv(ws, 60, ref="A")
    b = _inv(ws, 40, ref="B")
    pay = _pay(ws, 100)
    SettlementService.allocate(workspace_id=ws, credit_document_id=pay.id, debit_document_id=a.id,
                               amount="60")
    SettlementService.allocate(workspace_id=ws, credit_document_id=pay.id, debit_document_id=b.id,
                               amount="40")
    a.refresh_from_db()
    b.refresh_from_db()
    pay.refresh_from_db()
    assert a.status == b.status == SettlementDocument.SETTLED
    assert pay.status == SettlementDocument.SETTLED


@pytest.mark.django_db
def test_over_allocation_is_rejected():
    ws = uuid.uuid4()
    inv = _inv(ws, 50)
    pay = _pay(ws, 100)
    with pytest.raises(SettlementError):
        SettlementService.allocate(workspace_id=ws, credit_document_id=pay.id,
                                   debit_document_id=inv.id, amount="80")   # > invoice outstanding


@pytest.mark.django_db
def test_cross_partner_allocation_rejected():
    ws = uuid.uuid4()
    inv = _inv(ws, 100, partner="A")
    pay = _pay(ws, 100, partner="B")
    with pytest.raises(SettlementError):
        SettlementService.allocate(workspace_id=ws, credit_document_id=pay.id,
                                   debit_document_id=inv.id)


@pytest.mark.django_db
def test_fifo_auto_allocation():
    ws = uuid.uuid4()
    _inv(ws, 50, ref="OLD", date=dt.date(2026, 1, 1))
    _inv(ws, 50, ref="NEW", date=dt.date(2026, 2, 1))
    _pay(ws, 70, date=dt.date(2026, 2, 5))
    out = SettlementService.auto_allocate(workspace_id=ws, partner_ref="cust-1")
    assert out["allocated_amount"] == "70.00"
    old = SettlementDocument.objects.get(workspace_id=ws, document_ref="OLD")
    new = SettlementDocument.objects.get(workspace_id=ws, document_ref="NEW")
    assert old.status == SettlementDocument.SETTLED           # oldest fully paid first
    assert new.outstanding == Decimal("30.00")               # remainder on the newer invoice


@pytest.mark.django_db
def test_invoice_matched_aging():
    ws = uuid.uuid4()
    _inv(ws, 500, ref="OLD", date=dt.date(2026, 1, 1))       # ~2.5 months old
    inv2 = _inv(ws, 300, ref="NEW", date=dt.date(2026, 3, 10))
    _pay(ws, 300)                                            # settles part of the old invoice
    SettlementService.auto_allocate(workspace_id=ws, partner_ref="cust-1")
    aging = SettlementService.aging(ws, as_of=dt.date(2026, 3, 15))
    row = [r for r in aging["rows"] if r["partner_ref"] == "cust-1"][0]
    # old invoice 500 − 300 paid = 200 remaining (aged 60+); new 300 current
    assert aging["matched"] is True
    assert row["60+"] == "200.00" and row["current"] == "300.00"
    assert row["total"] == "500.00"
    _ = inv2


@pytest.mark.django_db
def test_unallocate_restores_balances():
    ws = uuid.uuid4()
    inv = _inv(ws, 100)
    pay = _pay(ws, 100)
    alloc = SettlementService.allocate(workspace_id=ws, credit_document_id=pay.id,
                                       debit_document_id=inv.id)
    SettlementService.unallocate(workspace_id=ws, allocation_id=alloc.id)
    inv.refresh_from_db()
    assert inv.status == SettlementDocument.OPEN and inv.outstanding == Decimal("100.00")
    assert not Allocation.objects.filter(workspace_id=ws, id=alloc.id).exists()


@pytest.mark.django_db
def test_outstanding_balance():
    ws = uuid.uuid4()
    _inv(ws, 100, ref="A")
    _inv(ws, 50, ref="B")
    pay = _pay(ws, 60)
    SettlementService.auto_allocate(workspace_id=ws, partner_ref="cust-1")
    _ = pay
    assert SettlementService.outstanding_balance(ws, "cust-1") == Decimal("90.00")  # 150 − 60


@pytest.mark.django_db
def test_register_document_idempotent():
    ws = uuid.uuid4()
    for _ in range(2):
        _inv(ws, 100, ref="DUP")
    assert SettlementDocument.objects.filter(
        workspace_id=ws, external_ref="d:cust-1:DUP:100").count() == 1


# ── workflow actions ────────────────────────────────────────────────────────────
def _run(ws):
    return types.SimpleNamespace(workspace_id=ws, initiated_by=None, id=uuid.uuid4(),
                                 record_id=None)


@pytest.mark.django_db
def test_action_register_and_auto_allocate():
    from apps.workflows.executors import exec_auto_allocate, exec_register_settlement_document
    ws = uuid.uuid4()
    inv_step = types.SimpleNamespace(config={
        "partner_ref": "p1", "direction": "debit", "amount": "100", "document_ref": "I1",
        "document_date": "2026-01-01"}, id="s1")
    pay_step = types.SimpleNamespace(config={
        "partner_ref": "p1", "direction": "credit", "amount": "100", "document_ref": "P1",
        "document_date": "2026-01-05"}, id="s2")
    assert exec_register_settlement_document(inv_step, _run(ws), {}, None)["registered"] is True
    exec_register_settlement_document(pay_step, _run(ws), {}, None)
    out = exec_auto_allocate(types.SimpleNamespace(config={"partner_ref": "p1"}, id="s3"),
                             _run(ws), {}, None)
    assert out["allocated_amount"] == "100.00"


@pytest.mark.django_db
def test_documents_are_workspace_isolated():
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    _inv(ws_a, 100)
    assert SettlementDocument.objects.filter(workspace_id=ws_a).exists()
    assert not SettlementDocument.objects.filter(workspace_id=ws_b).exists()


def test_settlement_registered_as_capability_and_actions():
    from apps.packaging.capabilities import capability_available
    from apps.workflows.executors import REGISTRY
    assert capability_available("settlement_engine")
    for action in ["action_register_settlement_document", "action_auto_allocate"]:
        assert action in REGISTRY
