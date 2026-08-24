"""
InventoryService (Phase P2.4) — the transactional stock engine.

Every quantity change locks the ``StockLevel`` row (``select_for_update``) inside a transaction,
so concurrent receipts/issues can never race on the on-hand or cost. Two costing methods are
supported per item:

  * **Weighted average** — receipts roll a single moving-average cost; issues leave the average
    unchanged and relieve at that average.
  * **FIFO** — receipts open ``FIFOLayer`` rows; issues consume the oldest layers first and the
    issue cost is the sum of the consumed layer costs.

Each movement is written immutably to ``StockMovement`` and, when a posting rule exists, posts to
the GL through the P2.2 ``GLBus`` (``inventory.received`` / ``inventory.issued`` / ``inventory.adjusted``).
"""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory

from .models import (
    ADJUSTMENT,
    FIFO,
    ISSUE,
    RECEIPT,
    TRANSFER_IN,
    TRANSFER_OUT,
    FIFOLayer,
    Item,
    StockLevel,
    StockMovement,
    Warehouse,
)

QTY = Decimal("0.0001")
MONEY = Decimal("0.01")
COST = Decimal("0.0001")
_ZERO = Decimal("0")


class InventoryError(Exception):
    """Raised on an invalid stock operation (negative stock, unknown item/warehouse, bad qty)."""


def _qty(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(QTY, rounding=ROUND_HALF_UP)


def _cost(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(COST, rounding=ROUND_HALF_UP)


def _money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _emit(workspace_id, movement, actor_id=None):
    from apps.eventstore.models import DomainEvent
    version = DomainEvent.objects.filter(aggregate_id=movement.id).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=f"inventory.{movement.movement_type}", workspace_id=workspace_id,
        aggregate_type="stock_movement", aggregate_id=movement.id, version=version,
        payload={"item_id": str(movement.item_id), "warehouse_id": str(movement.warehouse_id),
                 "quantity": str(movement.quantity), "total_cost": str(movement.total_cost)},
        actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _gl_post(workspace_id, event_type, item, total_cost, *, reference="", actor_id=None):
    """Post the movement to the GL via the bus. Returns ``None`` when no posting rule is
    configured for the event (a legitimate opt-out — the workspace simply doesn't book this
    event). A *configured* rule that fails (bad account, unbalanced) is NOT swallowed: it is
    recorded as a visible ``ledger.post.failed`` event and re-raised (P2.15 Blocker 3)."""
    from apps.ledger.services import GLBus, LedgerError, emit_post_failure
    try:
        entry = GLBus.post_event(
            workspace_id, event_type,
            {"amount": str(total_cost), "source_ref": reference,
             "inventory_account_code": item.inventory_account_code,
             "cogs_account_code": item.cogs_account_code,
             "memo": f"{event_type} {item.sku}"},
            source_module="inventory", source_ref=reference, actor_id=actor_id)
        return entry.id if entry is not None else None
    except LedgerError as exc:
        emit_post_failure(workspace_id, module="inventory", source_ref=reference,
                          error=str(exc), actor_id=actor_id)
        raise


class InventoryService:
    @staticmethod
    def _lock_level(workspace_id, item, warehouse) -> StockLevel:
        level = (StockLevel.objects.select_for_update()
                 .filter(workspace_id=workspace_id, item=item, warehouse=warehouse).first())
        if level is None:
            StockLevel.objects.get_or_create(
                workspace_id=workspace_id, item=item, warehouse=warehouse,
                defaults={"on_hand": _ZERO, "avg_cost": _ZERO, "value": _ZERO})
            level = (StockLevel.objects.select_for_update()
                     .get(workspace_id=workspace_id, item=item, warehouse=warehouse))
        return level

    @staticmethod
    def _resolve(workspace_id, item_id, warehouse_id):
        item = Item.objects.filter(workspace_id=workspace_id, id=item_id).first()
        if item is None:
            raise InventoryError("Item not found.")
        wh = Warehouse.objects.filter(workspace_id=workspace_id, id=warehouse_id).first()
        if wh is None:
            raise InventoryError("Warehouse not found.")
        return item, wh

    # ── receive ──────────────────────────────────────────────────────────────
    @staticmethod
    def receive(workspace_id, item_id, warehouse_id, quantity, unit_cost, *,
                occurred_at=None, location_id=None, reference="", memo="",
                movement_type=RECEIPT, post_gl=True, actor_id=None) -> StockMovement:
        qty = _qty(quantity)
        ucost = _cost(unit_cost)
        if qty <= 0:
            raise InventoryError("Receipt quantity must be positive.")
        occurred_at = occurred_at or timezone.now()
        with transaction.atomic():
            item, wh = InventoryService._resolve(workspace_id, item_id, warehouse_id)
            level = InventoryService._lock_level(workspace_id, item, wh)
            line_total = _money(qty * ucost)

            new_on_hand = _qty(level.on_hand + qty)
            new_value = _money(level.value + line_total)
            if item.valuation_method == FIFO:
                FIFOLayer.objects.create(
                    workspace_id=workspace_id, item=item, warehouse=wh, received_at=occurred_at,
                    original_qty=qty, remaining=qty, unit_cost=ucost)
            level.on_hand = new_on_hand
            level.value = new_value
            level.avg_cost = _cost(new_value / new_on_hand) if new_on_hand > 0 else _ZERO
            level.save(update_fields=["on_hand", "value", "avg_cost", "updated_at"])

            mv = StockMovement.objects.create(
                workspace_id=workspace_id, item=item, warehouse=wh, location_id=location_id,
                movement_type=movement_type, quantity=qty, unit_cost=ucost, total_cost=line_total,
                on_hand_after=new_on_hand, occurred_at=occurred_at, reference=reference, memo=memo,
                created_by=uuid.UUID(str(actor_id)) if actor_id else None)
            if post_gl and movement_type == RECEIPT:
                mv.journal_entry_id = _gl_post(workspace_id, "inventory.received", item, line_total,
                                               reference=reference, actor_id=actor_id)
                if mv.journal_entry_id:
                    mv.save(update_fields=["journal_entry_id"])
            _emit(workspace_id, mv, actor_id)
            return mv

    # ── issue ────────────────────────────────────────────────────────────────
    @staticmethod
    def issue(workspace_id, item_id, warehouse_id, quantity, *, occurred_at=None,
              location_id=None, reference="", memo="", movement_type=ISSUE,
              allow_negative=False, post_gl=True, actor_id=None) -> StockMovement:
        qty = _qty(quantity)
        if qty <= 0:
            raise InventoryError("Issue quantity must be positive.")
        occurred_at = occurred_at or timezone.now()
        with transaction.atomic():
            item, wh = InventoryService._resolve(workspace_id, item_id, warehouse_id)
            level = InventoryService._lock_level(workspace_id, item, wh)
            if not allow_negative and qty > level.on_hand:
                raise InventoryError(
                    f"Insufficient stock for {item.sku}: on hand {level.on_hand}, requested {qty}.")

            if item.valuation_method == FIFO:
                total = InventoryService._consume_fifo(workspace_id, item, wh, qty)
            else:
                total = _money(level.avg_cost * qty)

            new_on_hand = _qty(level.on_hand - qty)
            new_value = _money(level.value - total)
            level.on_hand = new_on_hand
            level.value = new_value if new_on_hand > 0 else _ZERO
            if new_on_hand <= 0:
                level.value = _ZERO
            # average stays constant on issue; recompute defensively for residual rounding
            level.avg_cost = _cost(level.value / new_on_hand) if new_on_hand > 0 else level.avg_cost
            level.save(update_fields=["on_hand", "value", "avg_cost", "updated_at"])

            unit = _cost(total / qty) if qty > 0 else _ZERO
            mv = StockMovement.objects.create(
                workspace_id=workspace_id, item=item, warehouse=wh, location_id=location_id,
                movement_type=movement_type, quantity=-qty, unit_cost=unit, total_cost=total,
                on_hand_after=new_on_hand, occurred_at=occurred_at, reference=reference, memo=memo,
                created_by=uuid.UUID(str(actor_id)) if actor_id else None)
            if post_gl and movement_type == ISSUE:
                mv.journal_entry_id = _gl_post(workspace_id, "inventory.issued", item, total,
                                               reference=reference, actor_id=actor_id)
                if mv.journal_entry_id:
                    mv.save(update_fields=["journal_entry_id"])
            _emit(workspace_id, mv, actor_id)
            return mv

    @staticmethod
    def _consume_fifo(workspace_id, item, warehouse, qty) -> Decimal:
        """Deplete the oldest open layers to satisfy ``qty``; returns the total consumed cost."""
        remaining = qty
        total = _ZERO
        layers = (FIFOLayer.objects.select_for_update()
                  .filter(workspace_id=workspace_id, item=item, warehouse=warehouse, remaining__gt=0)
                  .order_by("received_at", "created_at"))
        for layer in layers:
            if remaining <= 0:
                break
            take = min(layer.remaining, remaining)
            total += take * layer.unit_cost
            layer.remaining = _qty(layer.remaining - take)
            layer.save(update_fields=["remaining", "updated_at"])
            remaining = _qty(remaining - take)
        if remaining > 0:
            # Allowed only under allow_negative; cost the shortfall at the last/zero cost.
            last = (FIFOLayer.objects.filter(workspace_id=workspace_id, item=item, warehouse=warehouse)
                    .order_by("-received_at").first())
            total += remaining * (last.unit_cost if last else _ZERO)
        return _money(total)

    # ── adjust ───────────────────────────────────────────────────────────────
    @staticmethod
    def adjust(workspace_id, item_id, warehouse_id, quantity_delta, *, unit_cost=None,
               occurred_at=None, reference="", memo="", post_gl=True, actor_id=None) -> StockMovement:
        delta = _qty(quantity_delta)
        if delta == 0:
            raise InventoryError("Adjustment quantity cannot be zero.")
        if delta > 0:
            item = Item.objects.filter(workspace_id=workspace_id, id=item_id).first()
            uc = unit_cost if unit_cost is not None else (item.standard_cost if item else 0)
            return InventoryService.receive(
                workspace_id, item_id, warehouse_id, delta, uc, occurred_at=occurred_at,
                reference=reference, memo=memo, movement_type=ADJUSTMENT, post_gl=post_gl, actor_id=actor_id)
        return InventoryService.issue(
            workspace_id, item_id, warehouse_id, -delta, occurred_at=occurred_at, reference=reference,
            memo=memo, movement_type=ADJUSTMENT, allow_negative=True, post_gl=post_gl, actor_id=actor_id)

    # ── transfer ─────────────────────────────────────────────────────────────
    @staticmethod
    def transfer(workspace_id, item_id, from_warehouse_id, to_warehouse_id, quantity, *,
                 occurred_at=None, reference="", memo="", allow_negative=False, actor_id=None) -> dict:
        if str(from_warehouse_id) == str(to_warehouse_id):
            raise InventoryError("Source and destination warehouses must differ.")
        occurred_at = occurred_at or timezone.now()
        with transaction.atomic():
            out = InventoryService.issue(
                workspace_id, item_id, from_warehouse_id, quantity, occurred_at=occurred_at,
                reference=reference, memo=memo, movement_type=TRANSFER_OUT,
                allow_negative=allow_negative, post_gl=False, actor_id=actor_id)
            # Move at the relieved cost so total inventory value is conserved (cost-neutral transfer).
            unit_cost = abs(out.unit_cost)
            inn = InventoryService.receive(
                workspace_id, item_id, to_warehouse_id, quantity, unit_cost, occurred_at=occurred_at,
                reference=reference, memo=memo, movement_type=TRANSFER_IN, post_gl=False, actor_id=actor_id)
            return {"out": out, "in": inn}

    # ── reports ──────────────────────────────────────────────────────────────
    @staticmethod
    def stock_balance(workspace_id, *, warehouse_id=None, item_id=None) -> list[dict]:
        qs = StockLevel.objects.filter(workspace_id=workspace_id).select_related("item", "warehouse")
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if item_id:
            qs = qs.filter(item_id=item_id)
        rows = []
        for lvl in qs.order_by("item__sku"):
            rows.append({"item_id": str(lvl.item_id), "sku": lvl.item.sku, "item_name": lvl.item.name,
                         "warehouse_id": str(lvl.warehouse_id), "warehouse_code": lvl.warehouse.code,
                         "on_hand": str(_qty(lvl.on_hand)), "avg_cost": str(_cost(lvl.avg_cost)),
                         "value": str(_money(lvl.value))})
        return rows

    @staticmethod
    def valuation(workspace_id, *, warehouse_id=None) -> dict:
        rows = InventoryService.stock_balance(workspace_id, warehouse_id=warehouse_id)
        total = sum((Decimal(r["value"]) for r in rows), _ZERO)
        return {"rows": rows, "total_value": str(_money(total))}

    @staticmethod
    def movement_history(workspace_id, *, item_id=None, warehouse_id=None, limit=200) -> list[dict]:
        qs = StockMovement.objects.filter(workspace_id=workspace_id).select_related("item", "warehouse")
        if item_id:
            qs = qs.filter(item_id=item_id)
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        rows = []
        for mv in qs.order_by("-occurred_at", "-created_at")[:limit]:
            rows.append({"id": str(mv.id), "item_id": str(mv.item_id), "sku": mv.item.sku,
                         "warehouse_code": mv.warehouse.code, "movement_type": mv.movement_type,
                         "quantity": str(_qty(mv.quantity)), "unit_cost": str(_cost(mv.unit_cost)),
                         "total_cost": str(_money(mv.total_cost)), "on_hand_after": str(_qty(mv.on_hand_after)),
                         "occurred_at": mv.occurred_at.isoformat(), "reference": mv.reference,
                         "journal_entry_id": str(mv.journal_entry_id) if mv.journal_entry_id else None})
        return rows
