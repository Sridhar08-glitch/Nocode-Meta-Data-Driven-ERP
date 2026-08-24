"""
Settlement / Payment-Allocation services (Financial Platform).

``SettlementService`` is the single reusable entry point for matching payments/credits to invoices.
It maintains the settlement SUB-LEDGER (open items + allocations) and posts NO GL of its own — the
underlying invoice/payment already posted through ``GLBus``. It REUSES ``apps.credits`` for an optional
residual write-off. Every operation is workspace-scoped and idempotent on ``external_ref``.

Design: a DEBIT document (invoice/charge) is owed; a CREDIT document (payment/credit/deposit) pays it.
``allocate`` consumes the credit's unapplied amount against the debit's outstanding; ``auto_allocate``
applies open credits to the oldest open debits (FIFO); ``aging`` buckets each debit's OUTSTANDING by
its document date — the invoice-matched aging the line-level GL view could not produce.
"""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.solution_templates.documents import emit_event

from .models import CREDIT, DEBIT, Allocation, SettlementDocument

CENTS = Decimal("0.01")


class SettlementError(Exception):  # noqa: N818 — domain error
    pass


def _m(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


def _status_for(doc: SettlementDocument) -> str:
    if doc.allocated_amount <= 0:
        return SettlementDocument.OPEN
    if doc.allocated_amount >= doc.amount:
        return SettlementDocument.SETTLED
    return SettlementDocument.PARTIAL


class SettlementService:
    @staticmethod
    def register_document(*, workspace_id, partner_ref, direction, amount, doc_type="invoice",
                          document_ref="", document_date=None, due_date=None, account_code="",
                          currency="", source_module="", external_ref="", actor_id=None
                          ) -> SettlementDocument:
        """Register an open item (idempotent on ``external_ref``)."""
        if direction not in (DEBIT, CREDIT):
            raise SettlementError("direction must be 'debit' or 'credit'.")
        amt = _m(amount)
        if amt <= 0:
            raise SettlementError("Document amount must be positive.")
        with transaction.atomic():
            if external_ref:
                existing = (SettlementDocument.objects.select_for_update()
                            .filter(workspace_id=workspace_id, external_ref=external_ref)
                            .exclude(status=SettlementDocument.VOID).first())
                if existing is not None:
                    return existing
            doc = SettlementDocument.objects.create(
                workspace_id=workspace_id, partner_ref=str(partner_ref), direction=direction,
                doc_type=doc_type, document_ref=str(document_ref or ""), document_date=document_date,
                due_date=due_date, amount=amt, allocated_amount=Decimal("0"),
                account_code=str(account_code or ""), currency=currency,
                source_module=str(source_module or ""), external_ref=str(external_ref or ""),
                status=SettlementDocument.OPEN, created_by=_uid(actor_id))
        emit_event(workspace_id, "settlement_document", doc.id, "settlement.document.registered",
                   {"partner": doc.partner_ref, "direction": direction, "amount": str(amt),
                    "doc_type": doc_type}, actor_id)
        return doc

    @staticmethod
    def allocate(*, workspace_id, credit_document_id, debit_document_id, amount=None,
                 external_ref="", actor_id=None) -> Allocation:
        """Allocate a credit document against a debit document. Amount defaults to the max possible
        (min of the two outstandings). Validates same partner + opposite direction + no over-apply."""
        with transaction.atomic():
            if external_ref:
                dup = (Allocation.objects.filter(workspace_id=workspace_id, external_ref=external_ref)
                       .first())
                if dup is not None:
                    return dup
            credit = (SettlementDocument.objects.select_for_update()
                      .filter(workspace_id=workspace_id, id=credit_document_id).first())
            debit = (SettlementDocument.objects.select_for_update()
                     .filter(workspace_id=workspace_id, id=debit_document_id).first())
            if credit is None or debit is None:
                raise SettlementError("Settlement document not found.")
            if credit.direction != CREDIT or debit.direction != DEBIT:
                raise SettlementError("Allocate a CREDIT document onto a DEBIT document.")
            if credit.partner_ref != debit.partner_ref:
                raise SettlementError("Documents belong to different partners.")
            avail_credit = credit.outstanding
            avail_debit = debit.outstanding
            want = _m(amount) if amount is not None else min(avail_credit, avail_debit)
            if want <= 0:
                raise SettlementError("Nothing to allocate (a document is fully settled).")
            if want > avail_credit or want > avail_debit:
                raise SettlementError(
                    f"Over-allocation: max {min(avail_credit, avail_debit)} allocatable.")
            alloc = Allocation.objects.create(
                workspace_id=workspace_id, credit_document=credit, debit_document=debit,
                amount=want, external_ref=str(external_ref or ""), created_by=_uid(actor_id))
            for doc in (credit, debit):
                doc.allocated_amount = _m(doc.allocated_amount + want)
                doc.status = _status_for(doc)
                doc.save(update_fields=["allocated_amount", "status", "updated_at"])
        emit_event(workspace_id, "settlement_document", debit.id, "settlement.allocated",
                   {"partner": debit.partner_ref, "amount": str(want),
                    "credit": str(credit.id), "debit": str(debit.id)}, actor_id)
        return alloc

    @staticmethod
    def auto_allocate(*, workspace_id, partner_ref, actor_id=None) -> dict:
        """FIFO: apply each open credit document (oldest first) to the oldest open debit documents
        until exhausted. Returns counts + total allocated."""
        credits = list(SettlementDocument.objects.filter(
            workspace_id=workspace_id, partner_ref=str(partner_ref), direction=CREDIT,
            status__in=[SettlementDocument.OPEN, SettlementDocument.PARTIAL]
        ).order_by("document_date", "created_at"))
        total, count = Decimal("0"), 0
        for credit in credits:
            while credit.outstanding > 0:
                debit = (SettlementDocument.objects.filter(
                    workspace_id=workspace_id, partner_ref=str(partner_ref), direction=DEBIT,
                    status__in=[SettlementDocument.OPEN, SettlementDocument.PARTIAL])
                    .order_by("document_date", "created_at").first())
                if debit is None or debit.outstanding <= 0:
                    break
                alloc = SettlementService.allocate(
                    workspace_id=workspace_id, credit_document_id=credit.id,
                    debit_document_id=debit.id, actor_id=actor_id)
                total += alloc.amount
                count += 1
                credit.refresh_from_db()
        return {"allocations": count, "allocated_amount": str(_m(total))}

    @staticmethod
    def unallocate(*, workspace_id, allocation_id, actor_id=None) -> dict:
        """Reverse an allocation — restore both documents' outstanding. (Sub-ledger only; no GL.)"""
        with transaction.atomic():
            alloc = (Allocation.objects.select_for_update()
                     .filter(workspace_id=workspace_id, id=allocation_id).first())
            if alloc is None:
                return {"unallocated": False, "reason": "not_found"}
            for doc in (alloc.credit_document, alloc.debit_document):
                locked = SettlementDocument.objects.select_for_update().get(id=doc.id)
                locked.allocated_amount = _m(locked.allocated_amount - alloc.amount)
                locked.status = _status_for(locked)
                locked.save(update_fields=["allocated_amount", "status", "updated_at"])
            amount = alloc.amount
            alloc.delete()
        return {"unallocated": True, "amount": str(amount)}

    @staticmethod
    def outstanding_balance(workspace_id, partner_ref, *, direction=DEBIT) -> Decimal:
        total = Decimal("0")
        for doc in SettlementDocument.objects.filter(
                workspace_id=workspace_id, partner_ref=str(partner_ref), direction=direction
        ).exclude(status=SettlementDocument.VOID):
            total += doc.outstanding
        return _m(total)

    @staticmethod
    def aging(workspace_id, *, direction=DEBIT, as_of=None, buckets=(30, 60, 90)) -> dict:
        """Invoice-matched aging: bucket each document's OUTSTANDING by its document date."""
        import datetime as _dt
        as_of = as_of or _dt.date.today()  # noqa: DTZ011 — report as-of date
        labels = ["current", *[f"{b}+" for b in buckets]]
        partners: dict = {}
        for doc in SettlementDocument.objects.filter(
                workspace_id=workspace_id, direction=direction
        ).exclude(status__in=[SettlementDocument.VOID, SettlementDocument.SETTLED]):
            out = doc.outstanding
            if _m(out) == 0:
                continue
            slot = partners.setdefault(doc.partner_ref, {label_: Decimal("0") for label_ in labels})
            age = (as_of - doc.document_date).days if doc.document_date else 0
            bucket = "current"
            for b in buckets:
                if age >= b:
                    bucket = f"{b}+"
            slot[bucket] += out
        rows, totals, grand = [], {label_: Decimal("0") for label_ in labels}, Decimal("0")
        for partner, slot in sorted(partners.items()):
            total = sum(slot.values(), Decimal("0"))
            grand += total
            for label_ in labels:
                totals[label_] += slot[label_]
            rows.append({"partner_ref": partner, "total": str(_m(total)),
                         **{label_: str(_m(slot[label_])) for label_ in labels}})
        return {"as_of": str(as_of), "direction": direction, "buckets": labels, "rows": rows,
                "totals": {label_: str(_m(totals[label_])) for label_ in labels},
                "grand_total": str(_m(grand)), "matched": True}
