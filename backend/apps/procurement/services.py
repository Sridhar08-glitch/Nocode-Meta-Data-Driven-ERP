"""
Procurement native services (Phase P2.5) — the integrity seams ONLY.

Everything configurable (entities/forms/views/dashboards/reports/roles/workflows/app/nav) is
provisioned by the Solution Template Framework (``blueprint.py``). This module owns just the
parts that demand native, transactional, audited logic and reuse of the integrity engines:

  * gapless document numbering           → apps.numbering.NumberingService
  * Goods-Receipt posting → stock        → apps.inventory.InventoryService.receive
  * Vendor-Bill posting → GL event       → apps.ledger.GLBus.post_event
  * audit trail                          → apps.eventstore DomainEvent

Document master data is read/written through ``RecordService`` so RBAC/ABAC/RLS apply; this
module never touches physical tables directly.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.records.services import RecordService, resolve_entity

from .blueprint import DOC_SEQUENCES

# entity slug → short event key (procurement.<key>.<action>)
EVENT_KEY = {
    "rfq": "rfq", "purchase_order": "po",
    "goods_receipt": "receipt", "vendor_bill": "bill",
}
# prefix per numbered document
_SEQ_DEFAULTS = {
    "rfq": {"name": "RFQ", "prefix": "RFQ-", "padding": 6},
    "purchase_order": {"name": "Purchase Order", "prefix": "PO-", "padding": 6},
    "goods_receipt": {"name": "Goods Receipt", "prefix": "GR-", "padding": 6},
    "vendor_bill": {"name": "Vendor Bill", "prefix": "VB-", "padding": 6},
}


class ProcurementError(Exception):  # noqa: N818 — domain error
    pass


@dataclass
class _Actor:
    """Minimal member the permissions layer understands (reads user_id/id/role/custom_role_id)."""
    user_id: uuid.UUID
    id: uuid.UUID
    role: str = "owner"
    custom_role_id = None


def _system_member(actor_id):
    a = uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)
    return _Actor(user_id=a, id=a)


def _emit(workspace_id, aggregate_type, aggregate_id, event_type, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    agg = uuid.UUID(str(aggregate_id))
    version = DomainEvent.objects.filter(
        aggregate_id=agg, aggregate_type=aggregate_type).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type=aggregate_type, aggregate_id=agg, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _to_decimal(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return d


class ProcurementService:
    # ── numbering ────────────────────────────────────────────────────────────
    @staticmethod
    def ensure_sequences(workspace_id, *, actor_id=None):
        """Idempotently create the RFQ/PO/GR/VB number sequences for a workspace."""
        from apps.numbering.services import NumberingService
        for slug, defaults in _SEQ_DEFAULTS.items():
            NumberingService.ensure_sequence(
                workspace_id, slug, defaults=defaults, created_by=actor_id)

    # ── create a (numbered) document ──────────────────────────────────────────
    @staticmethod
    def create_document(*, workspace_id, entity_slug, data, member=None, actor_id=None):
        """Create a procurement document. Numbered docs (rfq/po/gr/vb) get a gapless number
        allocated INSIDE the same transaction as the record write, so a rollback also rolls
        back the sequence increment. Emits procurement.<key>.created."""
        from apps.numbering.services import NumberingService

        member = member or _system_member(actor_id)
        entity = resolve_entity(workspace_id, entity_slug)
        payload = dict(data or {})

        with transaction.atomic():
            if entity_slug in DOC_SEQUENCES and not payload.get("number"):
                ProcurementService.ensure_sequences(workspace_id, actor_id=actor_id)
                payload["number"] = NumberingService.allocate(
                    workspace_id, entity_slug, actor_id=actor_id,
                    context={"source_module": "procurement", "source_ref": entity_slug})
            record = RecordService.create_record(
                workspace_id=workspace_id, member=member, entity=entity, data=payload)

        key = EVENT_KEY.get(entity_slug)
        if key:
            _emit(workspace_id, entity_slug, record["id"], f"procurement.{key}.created",
                  {"number": record.get("number"), "entity": entity_slug}, actor_id)
        return record

    # ── approval transition (audit hook for workflow / manual approve) ────────
    @staticmethod
    def approve_document(*, workspace_id, entity_slug, record_id, member=None, actor_id=None):
        """Mark a document approved and emit procurement.<key>.approved."""
        member = member or _system_member(actor_id)
        entity = resolve_entity(workspace_id, entity_slug)
        record = RecordService.update_record(
            workspace_id=workspace_id, member=member, entity=entity,
            record_id=record_id, data={"status": "approved"})
        key = EVENT_KEY.get(entity_slug)
        if key:
            _emit(workspace_id, entity_slug, record_id, f"procurement.{key}.approved",
                  {"number": record.get("number")}, actor_id)
        return record

    # ── Goods Receipt → Inventory ledger (native integrity) ───────────────────
    @staticmethod
    def post_goods_receipt(*, workspace_id, record_id, member=None, actor_id=None):
        """Post a Goods Receipt into the Inventory ledger. Idempotent (a receipt already in
        'posted' status is a no-op). Each line increases stock via the Inventory Engine — we
        never duplicate inventory logic. Emits procurement.receipt.posted."""
        from apps.inventory.models import Item, Warehouse
        from apps.inventory.services import InventoryService

        member = member or _system_member(actor_id)
        gr_entity = resolve_entity(workspace_id, "goods_receipt")
        gr = RecordService.retrieve_record(
            workspace_id=workspace_id, member=member, entity=gr_entity, record_id=record_id)
        if gr.get("status") == "posted":
            return gr  # idempotent

        warehouse_code = (gr.get("warehouse_code") or "MAIN").strip() or "MAIN"
        warehouse, _ = Warehouse.objects.get_or_create(
            workspace_id=workspace_id, code=warehouse_code,
            defaults={"name": warehouse_code})

        line_entity = resolve_entity(workspace_id, "goods_receipt_line")
        lines = RecordService.list_records(
            workspace_id=workspace_id, member=member, entity=line_entity,
            filter_source={"field": "goods_receipt", "op": "=", "value": str(record_id)})

        movements = []
        for line in lines:
            sku = (line.get("item_sku") or "").strip()
            qty = _to_decimal(line.get("quantity"))
            cost = _to_decimal(line.get("unit_cost")) or Decimal("0")
            if not sku or qty is None or qty <= 0:
                continue  # nothing to receive for this line
            item, _ = Item.objects.get_or_create(
                workspace_id=workspace_id, sku=sku, defaults={"name": sku})
            mv = InventoryService.receive(
                workspace_id, item.id, warehouse.id, qty, cost,
                reference=gr.get("number") or "", memo="Goods receipt",
                actor_id=actor_id)
            movements.append(str(mv.id))

        gr = RecordService.update_record(
            workspace_id=workspace_id, member=member, entity=gr_entity,
            record_id=record_id, data={"status": "posted"})
        _emit(workspace_id, "goods_receipt", record_id, "procurement.receipt.posted",
              {"number": gr.get("number"), "warehouse": warehouse_code,
               "movements": movements, "lines": len(movements)}, actor_id)
        return gr

    # ── Vendor Bill → GL event (native integrity) ─────────────────────────────
    @staticmethod
    def post_vendor_bill(*, workspace_id, record_id, member=None, actor_id=None):
        """Post a Vendor Bill: emit the GL event (Accounting posts a JE if a PostingRule for
        'vendor_bill.posted' exists; otherwise no-op — the event contract exists regardless).
        Idempotent. Emits procurement.bill.posted."""
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure

        member = member or _system_member(actor_id)
        vb_entity = resolve_entity(workspace_id, "vendor_bill")
        vb = RecordService.retrieve_record(
            workspace_id=workspace_id, member=member, entity=vb_entity, record_id=record_id)
        if vb.get("status") == "posted":
            return vb  # idempotent

        number = vb.get("number") or ""
        amount = _to_decimal(vb.get("amount")) or Decimal("0")
        # No PostingRule configured ⇒ post_event returns None (legitimate opt-out, no JE). A
        # configured rule that FAILS is recorded + re-raised, never silently dropped (Blocker 3).
        try:
            entry = GLBus.post_event(
                workspace_id, "vendor_bill.posted",
                {"amount": str(amount), "memo": f"Vendor bill {number}", "source_ref": number},
                source_module="procurement", source_ref=number, actor_id=actor_id)
            journal_entry_id = str(entry.id) if entry is not None else None
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="procurement", source_ref=number,
                              error=str(exc), actor_id=actor_id)
            raise

        vb = RecordService.update_record(
            workspace_id=workspace_id, member=member, entity=vb_entity,
            record_id=record_id, data={"status": "posted"})
        _emit(workspace_id, "vendor_bill", record_id, "procurement.bill.posted",
              {"number": number, "amount": str(amount),
               "journal_entry_id": journal_entry_id}, actor_id)
        return vb
