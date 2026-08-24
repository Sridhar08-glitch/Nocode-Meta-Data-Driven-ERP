"""
Manufacturing + MRP (Phase P2.12) — native engine validation (BOM explosion/MRP/costing/OEE),
the production-order lifecycle (release→reserve→issue→complete) with cost rollup + finished-goods
+ lot traceability, quality, and framework install. Covers spec Modules 6/14/29/42/53/54/57/58/62.
"""
import uuid
from decimal import Decimal

import pytest

from apps.eventstore.models import DomainEvent
from apps.inventory.models import Item
from apps.manufacturing import engines
from apps.manufacturing.blueprint import (
    build_manufacturing_manifest,
    seed_manufacturing_template,
)
from apps.manufacturing.engines import BOMError
from apps.manufacturing.models import (
    BillOfMaterials,
    MaterialReservation,
    ProductionCost,
    ProductionOrder,
    StockLot,
)
from apps.manufacturing.services import (
    BOMService,
    CostingService,
    MRPService,
    ProductionOrderService,
    QualityService,
    TraceabilityService,
)
from apps.permissions.models import Role
from apps.solution_templates import services as st
from apps.solution_templates.validators import validate_solution_manifest
from apps.studio.models import Application

A = str(uuid.uuid4())


# ── Module 6: BOM explosion (multi-level + cycle) ────────────────────────────
def test_bom_explosion_multilevel():
    # 100 bikes → 2 wheels + 1 frame each; each wheel → 36 spokes.
    bike, wheel, frame, spoke = "bike", "wheel", "frame", "spoke"
    comps = {
        bike: [{"component_item_id": wheel, "quantity": 2},
               {"component_item_id": frame, "quantity": 1}],
        wheel: [{"component_item_id": spoke, "quantity": 36}],
    }
    reqs = engines.bom_explode(bike, 100, comps)
    assert reqs[wheel] == Decimal("200")
    assert reqs[frame] == Decimal("100")
    assert reqs[spoke] == Decimal("7200")   # 200 wheels × 36


def test_bom_explosion_scrap():
    comps = {"p": [{"component_item_id": "c", "quantity": 2, "scrap_percent": 10}]}
    assert engines.bom_explode("p", 100, comps)["c"] == Decimal("220.0")  # 200 × 1.10


def test_bom_explosion_circular():
    comps = {"a": [{"component_item_id": "b", "quantity": 1}],
             "b": [{"component_item_id": "a", "quantity": 1}]}
    with pytest.raises(BOMError):
        engines.bom_explode("a", 1, comps)


# ── Module 14: MRP ────────────────────────────────────────────────────────────
def test_mrp_plan_actions():
    rows = [{"item_id": "fg", "demand": 100, "available": 30, "has_bom": True},
            {"item_id": "rm", "demand": 50, "available": 80, "has_bom": False},
            {"item_id": "buy", "demand": 40, "available": 0, "has_bom": False}]
    out = {r["item_id"]: r for r in engines.mrp_plan(rows)}
    assert out["fg"]["net_requirement"] == Decimal("70") and out["fg"]["action"] == "manufacture"
    assert out["rm"]["net_requirement"] == Decimal("0") and out["rm"]["action"] == "none"
    assert out["buy"]["action"] == "purchase"


# ── Module 29/42/44: costing + OEE + yield (pure) ────────────────────────────
def test_standard_cost_engine():
    c = engines.standard_cost(material_cost=100, labor_minutes=120, labor_rate_per_hour=30,
                              overhead_percent=10)
    assert c["labor"] == "60.00"        # 2h × 30
    assert c["total"] == "176.00"       # (100 + 60) × 1.10


def test_oee_engine():
    o = engines.oee(planned_minutes=480, downtime_minutes=80, ideal_cycle_minutes=1,
                    good_qty=380, reject_qty=20)
    assert o["availability"] == pytest.approx(0.8333, abs=0.001)  # 400/480
    assert o["quality"] == 0.95                                    # 380/400


def test_yield_percent():
    assert engines.yield_percent(input_qty=100, output_qty=92) == 92.0


# ── framework provisioning ────────────────────────────────────────────────────
def test_manifest_validates_clean():
    assert validate_solution_manifest(build_manufacturing_manifest()) == []


@pytest.mark.django_db
def test_install_provisions_roles_and_app():
    ws = uuid.uuid4()
    st.install(template_id=seed_manufacturing_template().id, workspace_id=ws, installed_by=None)
    assert Role.objects.filter(workspace_id=ws, slug="manufacturing_manager").exists()
    assert Role.objects.filter(workspace_id=ws, slug="quality_inspector").exists()
    assert Application.objects.filter(workspace_id=ws, slug="manufacturing").exists()


# ── Modules 17/30/33/34/40/53/57: production order lifecycle ─────────────────
def _setup_bom(ws):
    product = Item.objects.create(workspace_id=ws, sku="BIKE", name="Bike",
                                  valuation_method="standard")
    c1 = Item.objects.create(workspace_id=ws, sku="C1", name="Wheel",
                             valuation_method="standard", standard_cost=Decimal("10"))
    c2 = Item.objects.create(workspace_id=ws, sku="C2", name="Spoke",
                             valuation_method="standard", standard_cost=Decimal("5"))
    bom = BOMService.create_bom(
        workspace_id=ws, product_item_id=product.id, quantity=1,
        components=[{"component_item_id": str(c1.id), "quantity": 2},
                    {"component_item_id": str(c2.id), "quantity": 3}], actor_id=A)
    BOMService.approve_bom(workspace_id=ws, bom_id=bom.id, actor_id=A)
    return product, bom


@pytest.mark.django_db
def test_bom_create_and_approve_audit():
    ws = uuid.uuid4()
    _setup_bom(ws)
    bom = BillOfMaterials.objects.get(workspace_id=ws)
    assert bom.number == "BOM-000001" and bom.status == "active"
    assert DomainEvent.objects.filter(event_type="manufacturing.bom.approved").exists()


@pytest.mark.django_db
def test_full_production_lifecycle_with_costing_and_traceability():
    from apps.ledger.provisioning import provision_accounting

    ws = uuid.uuid4()
    product, bom = _setup_bom(ws)
    provision_accounting(ws)  # WIP/FG postings now land (silent-swallow removed — Blocker 3)

    mo = ProductionOrderService.create_order(
        workspace_id=ws, product_item_id=product.id, quantity=10, bom_id=bom.id, actor_id=A)
    assert mo.number == "MO-000001"
    assert DomainEvent.objects.filter(event_type="manufacturing.order.created").exists()

    ProductionOrderService.release_order(workspace_id=ws, order_id=mo.id, actor_id=A)
    # 10 bikes → 20 wheels + 30 spokes reserved.
    res = {str(r.component_item_id): r for r in MaterialReservation.objects.filter(
        workspace_id=ws, production_order_id=mo.id)}
    assert len(res) == 2
    assert DomainEvent.objects.filter(event_type="manufacturing.order.released").exists()

    mo = ProductionOrderService.issue_materials(workspace_id=ws, order_id=mo.id, actor_id=A)
    # material = 20×10 + 30×5 = 350
    assert mo.material_cost == Decimal("350.00")
    assert mo.status == "in_progress"
    assert ProductionCost.objects.filter(workspace_id=ws, cost_type="material").count() == 2
    assert DomainEvent.objects.filter(event_type="manufacturing.order.started").exists()

    mo = ProductionOrderService.complete_order(workspace_id=ws, order_id=mo.id, good_qty=10,
                                               overhead_percent=10, actor_id=A)
    # overhead = 10% of (350 + 0) = 35 ; total = 385
    assert mo.overhead_cost == Decimal("35.00")
    assert mo.total_cost == Decimal("385.00")
    assert mo.status == "completed"
    assert DomainEvent.objects.filter(event_type="manufacturing.order.completed").exists()

    # Finished-goods lot created with traceability to consumed components.
    lot = StockLot.objects.get(workspace_id=ws, production_order_id=mo.id)
    trace = TraceabilityService.trace(workspace_id=ws, lot_id=lot.id)
    assert trace["production_order"] == "MO-000001"
    assert len(trace["components"]) == 2

    ProductionOrderService.close_order(workspace_id=ws, order_id=mo.id, actor_id=A)
    assert ProductionOrder.objects.get(id=mo.id).status == "closed"


# ── Module 14/58: MRP service + costing service ──────────────────────────────
@pytest.mark.django_db
def test_mrp_service_and_standard_cost():
    ws = uuid.uuid4()
    product, _ = _setup_bom(ws)
    result = MRPService.run_mrp(
        workspace_id=ws, demand=[{"item_id": str(product.id), "demand": 100, "available": 20}],
        actor_id=A)
    assert result["shortages"] == 1
    assert result["results"][0]["action"] == "manufacture"  # product has a BOM
    assert DomainEvent.objects.filter(event_type="manufacturing.mrp.completed").exists()

    cost = CostingService.standard_cost(workspace_id=ws, product_item_id=product.id, quantity=1)
    # material per unit = 2×10 + 3×5 = 35; overhead 10% → 38.50
    assert cost["material"] == "35.00" and cost["total"] == "38.50"


# ── Module 23/53: quality ─────────────────────────────────────────────────────
@pytest.mark.django_db
def test_quality_pass_and_fail_events():
    ws = uuid.uuid4()
    QualityService.record_check(workspace_id=ws, production_order_id=uuid.uuid4(), name="Final",
                                sampled_qty=10, passed_qty=10, failed_qty=0, actor_id=A)
    QualityService.record_check(workspace_id=ws, production_order_id=uuid.uuid4(), name="Final",
                                sampled_qty=10, passed_qty=8, failed_qty=2, actor_id=A)
    assert DomainEvent.objects.filter(event_type="manufacturing.quality.passed").exists()
    assert DomainEvent.objects.filter(event_type="manufacturing.quality.failed").exists()


# ── Module 63: END-TO-END readiness (Inventory + Procurement + Accounting reuse) ──────────
@pytest.mark.django_db
def test_e2e_mrp_to_finished_goods_with_real_inventory_and_gl():
    """Scenario 1/2/3/6/7/8/9: MRP shortage → (inventory stocked by goods receipt) → production
    order → reserve → ISSUE consumes the real Inventory ledger → quality → FG receipt updates real
    Inventory → balanced GL via GLBus → lot traceability. Proves NO duplicate inventory/accounting/
    product master: manufacturing reuses Item/Warehouse/StockLevel/StockMovement + GLBus only."""
    from apps.inventory.models import Item as InvItem
    from apps.inventory.models import StockLevel, StockMovement, Warehouse
    from apps.inventory.services import InventoryService
    from apps.ledger.models import JournalEntry
    from apps.ledger.provisioning import provision_accounting

    ws = uuid.uuid4()
    # Inventory master (REUSED — no ManufacturingProduct model exists).
    product = InvItem.objects.create(workspace_id=ws, sku="FG", name="Bike",
                                     valuation_method="average")
    c1 = InvItem.objects.create(workspace_id=ws, sku="C1", name="Wheel",
                                valuation_method="average")
    c2 = InvItem.objects.create(workspace_id=ws, sku="C2", name="Spoke",
                                valuation_method="average")
    wh = Warehouse.objects.create(workspace_id=ws, code="MAIN", name="Main")
    # Goods receipt (procurement → inventory) stocks the components.
    InventoryService.receive(ws, c1.id, wh.id, 100, "10")
    InventoryService.receive(ws, c2.id, wh.id, 100, "5")
    # Provision the standard chart so manufacturing's WIP/FG postings land (accounting flows
    # ONLY through GLBus). post_gl=False on the inventory issue/receive avoids double-posting.
    provision_accounting(ws)

    # BOM + MRP shortage detection.
    bom = BOMService.create_bom(
        workspace_id=ws, product_item_id=product.id, quantity=1,
        components=[{"component_item_id": str(c1.id), "quantity": 2},
                    {"component_item_id": str(c2.id), "quantity": 3}], actor_id=A)
    BOMService.approve_bom(workspace_id=ws, bom_id=bom.id, actor_id=A)
    mrp = MRPService.run_mrp(workspace_id=ws,
                             demand=[{"item_id": str(product.id), "demand": 10}], actor_id=A)
    assert mrp["shortages"] == 1 and mrp["results"][0]["action"] == "manufacture"

    # Production: create → release → issue (consume inventory) → quality → complete (FG receipt).
    mo = ProductionOrderService.create_order(
        workspace_id=ws, product_item_id=product.id, quantity=10, bom_id=bom.id,
        warehouse_id=wh.id, actor_id=A)
    ProductionOrderService.release_order(workspace_id=ws, order_id=mo.id, actor_id=A)
    mo = ProductionOrderService.issue_materials(workspace_id=ws, order_id=mo.id, actor_id=A)

    # Inventory CONSUMED from the real ledger (reuse, not a duplicate table).
    assert StockLevel.objects.get(workspace_id=ws, item_id=c1.id).on_hand == Decimal("80.0000")
    assert StockLevel.objects.get(workspace_id=ws, item_id=c2.id).on_hand == Decimal("70.0000")
    assert StockMovement.objects.filter(workspace_id=ws, movement_type="issue").count() == 2
    assert mo.material_cost == Decimal("350.00")  # 20×10 + 30×5 (actual avg cost)

    QualityService.record_check(workspace_id=ws, production_order_id=mo.id, name="Final",
                                sampled_qty=10, passed_qty=10, failed_qty=0, actor_id=A)
    mo = ProductionOrderService.complete_order(workspace_id=ws, order_id=mo.id, good_qty=10,
                                               overhead_percent=10, actor_id=A)
    assert mo.total_cost == Decimal("385.00")     # 350 + 0 labor + 35 overhead

    # Finished goods RECEIVED into the real Inventory ledger.
    assert StockLevel.objects.get(workspace_id=ws, item_id=product.id).on_hand == Decimal("10.0000")

    # Accounting flowed through GLBus — balanced entries (GLBus.post rejects unbalanced).
    je = JournalEntry.objects.filter(workspace_id=ws, source_module="manufacturing")
    assert je.count() >= 2  # material consumption (WIP) + finished goods (WIP→FG)

    # Backward traceability: FG lot → production order → consumed components.
    lot = StockLot.objects.get(workspace_id=ws, production_order_id=mo.id)
    trace = TraceabilityService.trace(workspace_id=ws, lot_id=lot.id)
    assert trace["production_order"] == mo.number and len(trace["components"]) == 2
    # Audit chain (Module 53).
    for ev in ["manufacturing.order.created", "manufacturing.order.released",
               "manufacturing.order.started", "manufacturing.order.completed",
               "manufacturing.mrp.completed", "manufacturing.quality.passed"]:
        assert DomainEvent.objects.filter(event_type=ev).exists(), ev
