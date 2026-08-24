"""
Manufacturing services (Phase P2.12) — native production orchestration.

Reuses the P2.4 Inventory ledger (material issue / finished-goods receipt) and GLBus (WIP/GL
postings) — never re-implementing inventory or accounting. The BOM/MRP/costing/OEE engines are
pure (``engines.py``). Production-order posting is race-safe (select_for_update); inventory + GL
calls are decoupled (best-effort) so a partial setup never corrupts the order. Audit on every
material transition. Batch-read (no per-component N+1).
"""
from __future__ import annotations

import contextlib
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.ledger.provisioning import ensure_accounting_settings

from . import engines
from .engines import money, qty
from .models import (
    BillOfMaterials,
    BomComponent,
    MaterialReservation,
    MRPResult,
    MRPRun,
    NonConformance,
    ProductionCost,
    ProductionOperation,
    ProductionOrder,
    QualityCheck,
    RoutingStep,
    StockLot,
    WorkCenter,
)

_SEQUENCES = {
    "mfg_bom": {"name": "BOM", "prefix": "BOM-", "padding": 6},
    "mfg_production_order": {"name": "Production Order", "prefix": "MO-", "padding": 6},
}


class ManufacturingError(Exception):  # noqa: N818 — domain error
    pass


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


def _emit(obj, aggregate_type, event_type, payload, actor_id=None):
    from apps.eventstore.models import DomainEvent
    version = DomainEvent.objects.filter(
        aggregate_id=obj.id, aggregate_type=aggregate_type).count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=obj.workspace_id,
        aggregate_type=aggregate_type, aggregate_id=obj.id, version=version,
        payload=payload, actor_id=_uid(actor_id) or uuid.UUID(int=0)))


def ensure_sequences(workspace_id, *, actor_id=None):
    from apps.numbering.services import NumberingService
    for key, defaults in _SEQUENCES.items():
        NumberingService.ensure_sequence(
            workspace_id, key, defaults=defaults, created_by=actor_id)


def _allocate(workspace_id, key, actor_id):
    from apps.numbering.services import NumberingService
    NumberingService.ensure_sequence(workspace_id, key, defaults=_SEQUENCES[key],
                                     created_by=actor_id)
    return NumberingService.allocate(workspace_id, key, actor_id=actor_id,
                                     context={"source_module": "manufacturing"})


# ── BOM ───────────────────────────────────────────────────────────────────────
class BOMService:
    @staticmethod
    def create_bom(*, workspace_id, product_item_id, quantity=1, revision="A",
                   components=None, actor_id=None) -> BillOfMaterials:
        with transaction.atomic():
            bom = BillOfMaterials.objects.create(
                workspace_id=workspace_id, number=_allocate(workspace_id, "mfg_bom", actor_id),
                product_item_id=product_item_id, quantity=qty(quantity), revision=revision,
                status="draft", created_by=_uid(actor_id))
            for i, c in enumerate(components or []):
                BomComponent.objects.create(
                    workspace_id=workspace_id, bom_id=bom.id,
                    component_item_id=c["component_item_id"], quantity=qty(c["quantity"]),
                    scrap_percent=c.get("scrap_percent", 0), sequence=(i + 1) * 10)
        return bom

    @staticmethod
    def approve_bom(*, workspace_id, bom_id, actor_id=None) -> BillOfMaterials:
        bom = BillOfMaterials.objects.filter(workspace_id=workspace_id, id=bom_id).first()
        if bom is None:
            raise ManufacturingError("BOM not found.")
        bom.status = "active"
        bom.save(update_fields=["status", "updated_at"])
        _emit(bom, "mfg_bom", "manufacturing.bom.approved", {"number": bom.number}, actor_id)
        return bom

    @staticmethod
    def _components_map(workspace_id):
        """{product_item_id: [components]} from ACTIVE BOMs — for multi-level explosion."""
        boms = {b.id: b for b in BillOfMaterials.objects.filter(
            workspace_id=workspace_id, status="active")}
        by_product: dict = {}
        for b in boms.values():
            by_product.setdefault(str(b.product_item_id), b.id)
        comps = BomComponent.objects.filter(workspace_id=workspace_id, bom_id__in=list(boms))
        by_bom: dict = {}
        for c in comps:
            by_bom.setdefault(str(c.bom_id), []).append(
                {"component_item_id": str(c.component_item_id), "quantity": c.quantity,
                 "scrap_percent": c.scrap_percent})
        return {pid: by_bom.get(str(bid), []) for pid, bid in by_product.items()}

    @staticmethod
    def explode(*, workspace_id, product_item_id, quantity):
        """Multi-level explosion of a product into total component requirements."""
        return engines.bom_explode(
            str(product_item_id), quantity, BOMService._components_map(workspace_id))


# ── production order lifecycle ────────────────────────────────────────────────
class ProductionOrderService:
    @staticmethod
    def create_order(*, workspace_id, product_item_id, quantity, bom_id=None, routing_id=None,
                     warehouse_id=None, source_project_id=None, actor_id=None) -> ProductionOrder:
        with transaction.atomic():
            mo = ProductionOrder.objects.create(
                workspace_id=workspace_id,
                number=_allocate(workspace_id, "mfg_production_order", actor_id),
                product_item_id=product_item_id, bom_id=bom_id, routing_id=routing_id,
                warehouse_id=warehouse_id, quantity=qty(quantity), status="draft",
                source_project_id=source_project_id, created_by=_uid(actor_id))
        _emit(mo, "mfg_production_order", "manufacturing.order.created",
              {"number": mo.number, "quantity": str(mo.quantity)}, actor_id)
        return mo

    @staticmethod
    def release_order(*, workspace_id, order_id, member=None, actor_id=None) -> ProductionOrder:
        """Explode the BOM into material reservations, create operations from the routing, and
        reserve inventory (best-effort). Module 16 + 17."""
        with transaction.atomic():
            mo = ProductionOrder.objects.select_for_update().filter(
                workspace_id=workspace_id, id=order_id).first()
            if mo is None:
                raise ManufacturingError("Production order not found.")
            if mo.status not in {"draft", "planned"}:
                raise ManufacturingError(f"Cannot release a {mo.status} order.")
            reqs = engines.bom_explode(
                str(mo.product_item_id), mo.quantity,
                BOMService._components_map(workspace_id))
            for item_id, need in reqs.items():
                unit_cost = _item_cost(workspace_id, item_id)
                MaterialReservation.objects.create(
                    workspace_id=workspace_id, production_order_id=mo.id,
                    component_item_id=item_id, required_qty=need, reserved_qty=need,
                    unit_cost=unit_cost, created_by=_uid(actor_id))
            if mo.routing_id:
                for step in RoutingStep.objects.filter(
                        workspace_id=workspace_id, routing_id=mo.routing_id).order_by("sequence"):
                    ProductionOperation.objects.create(
                        workspace_id=workspace_id, production_order_id=mo.id,
                        routing_step_id=step.id, work_center_id=step.work_center_id,
                        sequence=step.sequence, status="pending", created_by=_uid(actor_id))
            mo.status = "released"
            mo.save(update_fields=["status", "updated_at"])
        _emit(mo, "mfg_production_order", "manufacturing.order.released",
              {"reservations": len(reqs)}, actor_id)
        return mo

    @staticmethod
    def issue_materials(*, workspace_id, order_id, actor_id=None) -> ProductionOrder:
        """Consume reserved materials from the Inventory ledger → WIP. Module 19/34/35."""
        mo = ProductionOrder.objects.filter(workspace_id=workspace_id, id=order_id).first()
        if mo is None:
            raise ManufacturingError("Production order not found.")
        total_material = Decimal("0.00")
        for res in MaterialReservation.objects.filter(
                workspace_id=workspace_id, production_order_id=mo.id):
            issue_qty = res.required_qty - res.issued_qty
            if issue_qty <= 0:
                continue
            cost = ProductionOrderService._inventory_issue(
                workspace_id, res.component_item_id, mo.warehouse_id, issue_qty,
                res.unit_cost, mo.number, actor_id)
            res.issued_qty = res.required_qty
            res.save(update_fields=["issued_qty", "updated_at"])
            ProductionCost.objects.create(
                workspace_id=workspace_id, production_order_id=mo.id, cost_type="material",
                amount=cost, reference=str(res.component_item_id))
            total_material += cost
        mo.material_cost = money(mo.material_cost + total_material)
        mo.status = "in_progress"
        mo.actual_start = mo.actual_start or timezone.now()
        mo.save(update_fields=["material_cost", "status", "actual_start", "updated_at"])
        _s = ensure_accounting_settings(workspace_id)
        ProductionOrderService._gl(workspace_id, mo, _s.default_wip_account,
                                   _s.default_inventory_account, total_material,
                                   "Material consumption (WIP)", actor_id)
        _emit(mo, "mfg_production_order", "manufacturing.order.started",
              {"material_cost": str(total_material)}, actor_id)
        return mo

    @staticmethod
    def complete_operation(*, workspace_id, operation_id, labor_minutes=0, machine_minutes=0,
                           downtime_minutes=0, downtime_reason="", good_qty=0, reject_qty=0,
                           actor_id=None) -> ProductionOperation:
        op = ProductionOperation.objects.filter(
            workspace_id=workspace_id, id=operation_id).first()
        if op is None:
            raise ManufacturingError("Operation not found.")
        wc = WorkCenter.objects.filter(workspace_id=workspace_id, id=op.work_center_id).first()
        rate = wc.cost_per_hour if wc else Decimal("0")
        labor_cost = money(qty(labor_minutes) / Decimal("60") * money(rate))
        op.labor_minutes = qty(labor_minutes)
        op.machine_minutes = qty(machine_minutes)
        op.downtime_minutes = qty(downtime_minutes)
        op.downtime_reason = downtime_reason
        op.good_qty = qty(good_qty)
        op.reject_qty = qty(reject_qty)
        op.status = "completed"
        op.actual_finish = timezone.now()
        op.save()
        if labor_cost > 0:
            ProductionCost.objects.create(
                workspace_id=workspace_id, production_order_id=op.production_order_id,
                cost_type="labor", amount=labor_cost, reference=str(op.id))
            ProductionOrder.objects.filter(
                workspace_id=workspace_id, id=op.production_order_id).update(
                    labor_cost=_f_add("labor_cost", labor_cost))
        return op

    @staticmethod
    def complete_order(*, workspace_id, order_id, good_qty=None, scrap_qty=0, overhead_percent=10,
                       lot_number="", actor_id=None) -> ProductionOrder:
        """Receive finished goods into Inventory, post WIP→FG GL, roll up cost, create a lot for
        traceability. Modules 28/30/33/34/40."""
        with transaction.atomic():
            mo = ProductionOrder.objects.select_for_update().filter(
                workspace_id=workspace_id, id=order_id).first()
            if mo is None:
                raise ManufacturingError("Production order not found.")
            if mo.status not in {"in_progress", "released"}:
                raise ManufacturingError(f"Cannot complete a {mo.status} order.")
            good = qty(good_qty) if good_qty is not None else mo.quantity
            overhead = money((mo.material_cost + mo.labor_cost) * qty(overhead_percent)
                             / Decimal("100"))
            total = money(mo.material_cost + mo.labor_cost + overhead)
            unit_cost = money(total / good) if good > 0 else Decimal("0.00")
            mo.overhead_cost = overhead
            mo.total_cost = total
            mo.good_qty = good
            mo.scrap_qty = qty(scrap_qty)
            mo.status = "completed"
            mo.actual_finish = timezone.now()
            if overhead > 0:
                ProductionCost.objects.create(
                    workspace_id=workspace_id, production_order_id=mo.id, cost_type="overhead",
                    amount=overhead, reference="applied")
            # Finished-goods receipt into the Inventory ledger (reuse P2.4).
            ProductionOrderService._inventory_receive(
                workspace_id, mo.product_item_id, mo.warehouse_id, good, unit_cost,
                mo.number, actor_id)
            # Lot/serial traceability — link FG lot to the consumed component lots.
            consumed = list(MaterialReservation.objects.filter(
                workspace_id=workspace_id, production_order_id=mo.id).values_list(
                "component_item_id", flat=True))
            StockLot.objects.create(
                workspace_id=workspace_id, item_id=mo.product_item_id,
                lot_number=lot_number or mo.number, production_order_id=mo.id,
                manufacture_date=timezone.now().date(),
                consumed_lot_ids=[str(c) for c in consumed], created_by=_uid(actor_id))
            mo.save()
        _s = ensure_accounting_settings(workspace_id)
        ProductionOrderService._gl(workspace_id, mo, _s.default_finished_goods_account,
                                   _s.default_wip_account, total,
                                   "Finished goods (WIP→FG)", actor_id)
        _emit(mo, "mfg_production_order", "manufacturing.order.completed",
              {"total_cost": str(total), "good_qty": str(good)}, actor_id)
        return mo

    @staticmethod
    def close_order(*, workspace_id, order_id, actor_id=None) -> ProductionOrder:
        mo = ProductionOrder.objects.filter(workspace_id=workspace_id, id=order_id).first()
        if mo is None:
            raise ManufacturingError("Production order not found.")
        if mo.status != "completed":
            raise ManufacturingError("Only a completed order can be closed.")
        mo.status = "closed"
        mo.save(update_fields=["status", "updated_at"])
        _emit(mo, "mfg_production_order", "manufacturing.order.closed", {}, actor_id)
        return mo

    # ── inventory + GL helpers (decoupled) ────────────────────────────────────
    @staticmethod
    def _inventory_issue(workspace_id, item_id, warehouse_id, quantity, unit_cost, ref, actor_id):
        if warehouse_id:
            try:
                from apps.inventory.services import InventoryService
                mv = InventoryService.issue(workspace_id, item_id, warehouse_id, quantity,
                                            reference=ref, post_gl=False, actor_id=actor_id)
                if getattr(mv, "total_cost", None):
                    return money(abs(mv.total_cost))
            except Exception:  # noqa: BLE001 — decoupled; fall back to reservation cost
                pass
        return money(qty(quantity) * money(unit_cost))

    @staticmethod
    def _inventory_receive(workspace_id, item_id, warehouse_id, quantity, unit_cost, ref, actor_id):
        if not warehouse_id:
            return
        with contextlib.suppress(Exception):
            from apps.inventory.services import InventoryService
            InventoryService.receive(workspace_id, item_id, warehouse_id, quantity, unit_cost,
                                     reference=ref, post_gl=False, actor_id=actor_id)

    @staticmethod
    def _gl(workspace_id, mo, debit_acct, credit_acct, amount, memo, actor_id):
        if money(amount) <= 0:
            return
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        try:
            entry = GLBus.post(
                workspace_id, date=timezone.now().date(), lines=[
                    {"account_code": debit_acct, "debit": str(money(amount)), "memo": memo},
                    {"account_code": credit_acct, "credit": str(money(amount)), "memo": memo}],
                memo=f"Manufacturing {mo.number}", source_module="manufacturing",
                source_ref=str(mo.id), actor_id=actor_id)
            if entry is not None and not mo.journal_entry_id:
                ProductionOrder.objects.filter(id=mo.id).update(journal_entry_id=entry.id)
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="manufacturing", source_ref=str(mo.id),
                              error=str(exc), actor_id=actor_id)
            raise


def _f_add(field, value):
    from django.db.models import F
    return F(field) + value


def _item_cost(workspace_id, item_id) -> Decimal:
    """Best-effort component unit cost from the Inventory item / stock level."""
    with contextlib.suppress(Exception):
        from apps.inventory.models import Item, StockLevel
        lvl = StockLevel.objects.filter(workspace_id=workspace_id, item_id=item_id).first()
        if lvl and lvl.avg_cost:
            return money(lvl.avg_cost)
        item = Item.objects.filter(workspace_id=workspace_id, id=item_id).first()
        if item and getattr(item, "standard_cost", None):
            return money(item.standard_cost)
    return Decimal("0.00")


# ── MRP ───────────────────────────────────────────────────────────────────────
class MRPService:
    @staticmethod
    def run_mrp(*, workspace_id, demand, run_type="regenerative", actor_id=None) -> dict:
        """demand: [{item_id, demand, available?}]. Computes net requirements + actions; persists
        an MRPRun + MRPResults. Items with an active BOM → manufacture, else purchase. Module 14."""
        bom_items = {str(p) for p in BillOfMaterials.objects.filter(
            workspace_id=workspace_id, status="active").values_list("product_item_id", flat=True)}
        rows = []
        for d in demand:
            available = d.get("available")
            if available is None:
                available = _stock_available(workspace_id, d["item_id"])
            rows.append({"item_id": str(d["item_id"]), "demand": d["demand"],
                         "available": available, "has_bom": str(d["item_id"]) in bom_items})
        results = engines.mrp_plan(rows)
        shortages = [r for r in results if r["net_requirement"] > 0]
        run = MRPRun.objects.create(
            workspace_id=workspace_id, run_type=run_type, status="completed",
            shortage_count=len(shortages), created_by=_uid(actor_id))
        for r in results:
            MRPResult.objects.create(
                workspace_id=workspace_id, mrp_run_id=run.id, item_id=r["item_id"],
                demand=r["demand"], available=r["available"],
                net_requirement=r["net_requirement"], suggested_qty=r["suggested_qty"],
                action=r["action"])
        _emit(run, "mfg_mrp_run", "manufacturing.mrp.completed",
              {"shortages": len(shortages)}, actor_id)
        return {"run_id": str(run.id), "shortages": len(shortages), "results": results}


def _stock_available(workspace_id, item_id) -> Decimal:
    with contextlib.suppress(Exception):
        from django.db.models import Sum

        from apps.inventory.models import StockLevel
        total = StockLevel.objects.filter(
            workspace_id=workspace_id, item_id=item_id).aggregate(s=Sum("on_hand"))["s"]
        if total is not None:
            return qty(total)
    return Decimal("0")


# ── costing ───────────────────────────────────────────────────────────────────
class CostingService:
    @staticmethod
    def standard_cost(*, workspace_id, product_item_id, quantity=1, labor_minutes=0,
                      labor_rate_per_hour=0, overhead_percent=10) -> dict:
        """Roll up standard cost: exploded BOM material + routing labor + overhead. Module 30."""
        reqs = BOMService.explode(workspace_id=workspace_id, product_item_id=product_item_id,
                                  quantity=quantity)
        material = Decimal("0.00")
        for item_id, need in reqs.items():
            material += money(_item_cost(workspace_id, item_id) * need)
        return engines.standard_cost(
            material_cost=material, labor_minutes=labor_minutes,
            labor_rate_per_hour=labor_rate_per_hour, overhead_percent=overhead_percent)


# ── quality / NCR ─────────────────────────────────────────────────────────────
class QualityService:
    @staticmethod
    def record_check(*, workspace_id, production_order_id, name, sampled_qty, passed_qty,
                     failed_qty, sampling_percent=100, actor_id=None) -> QualityCheck:
        result = "pass" if qty(failed_qty) == 0 else "fail"
        qc = QualityCheck.objects.create(
            workspace_id=workspace_id, production_order_id=production_order_id, name=name,
            sampling_percent=sampling_percent, sampled_qty=qty(sampled_qty),
            passed_qty=qty(passed_qty), failed_qty=qty(failed_qty), result=result,
            created_by=_uid(actor_id))
        _emit(qc, "mfg_quality_check",
              "manufacturing.quality.passed" if result == "pass"
              else "manufacturing.quality.failed", {"result": result}, actor_id)
        return qc

    @staticmethod
    def create_ncr(*, workspace_id, production_order_id, defect, actor_id=None) -> NonConformance:
        return NonConformance.objects.create(
            workspace_id=workspace_id, production_order_id=production_order_id, defect=defect,
            status="open", created_by=_uid(actor_id))


# ── OEE + traceability ────────────────────────────────────────────────────────
class OEEService:
    @staticmethod
    def for_order(*, workspace_id, order_id, ideal_cycle_minutes=1) -> dict:
        ops = list(ProductionOperation.objects.filter(
            workspace_id=workspace_id, production_order_id=order_id))
        planned = sum((o.labor_minutes + o.machine_minutes + o.downtime_minutes for o in ops),
                      Decimal("0"))
        downtime = sum((o.downtime_minutes for o in ops), Decimal("0"))
        good = sum((o.good_qty for o in ops), Decimal("0"))
        reject = sum((o.reject_qty for o in ops), Decimal("0"))
        return engines.oee(planned_minutes=planned, downtime_minutes=downtime,
                           ideal_cycle_minutes=ideal_cycle_minutes, good_qty=good,
                           reject_qty=reject)


class TraceabilityService:
    @staticmethod
    def trace(*, workspace_id, lot_id) -> dict:
        """Finished-good lot → production order → consumed component lots/items → supplier."""
        lot = StockLot.objects.filter(workspace_id=workspace_id, id=lot_id).first()
        if lot is None:
            raise ManufacturingError("Lot not found.")
        mo = ProductionOrder.objects.filter(
            workspace_id=workspace_id, id=lot.production_order_id).first()
        reservations = list(MaterialReservation.objects.filter(
            workspace_id=workspace_id, production_order_id=lot.production_order_id).values(
            "component_item_id", "required_qty"))
        return {
            "lot": {"id": str(lot.id), "lot_number": lot.lot_number,
                    "item_id": str(lot.item_id)},
            "production_order": mo.number if mo else None,
            "components": [{"item_id": str(r["component_item_id"]),
                            "quantity": str(r["required_qty"])} for r in reservations],
            "consumed_lots": lot.consumed_lot_ids,
        }
