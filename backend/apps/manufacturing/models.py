"""
Manufacturing native models (Phase P2.12) — a true ERP production engine.

BOM structures, routings, work centers, production orders/operations, material reservations,
production costs, quality, MRP results and lot traceability are NATIVE (multi-level BOM explosion,
finite scheduling, WIP/GL postings, race-safe material reservation — none expressible as metadata).
Products reuse the Inventory ``Item`` (referenced by id — no duplicate product master); material
issue / finished-goods receipt reuse the P2.4 Inventory ledger. Workspace-scoped (TenantModel) +
PostgreSQL RLS (migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 16, "decimal_places": 2, "default": 0}
QTY = {"max_digits": 16, "decimal_places": 4, "default": 0}


class WorkCenter(TenantModel):
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=150)
    center_type = models.CharField(max_length=20, default="machine")  # labor|machine|hybrid
    capacity_per_hour = models.DecimalField(**QTY)
    efficiency = models.DecimalField(max_digits=6, decimal_places=2, default=100)  # %
    cost_per_hour = models.DecimalField(**MONEY)
    asset_record_id = models.UUIDField(null=True, blank=True)   # → Assets metadata
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "mfg_work_centers"
        indexes = [models.Index(fields=["workspace_id", "is_active"])]


class BillOfMaterials(TenantModel):
    number = models.CharField(max_length=64, blank=True)
    product_item_id = models.UUIDField(db_index=True)            # → Inventory Item
    revision = models.CharField(max_length=20, default="A")
    quantity = models.DecimalField(**QTY)                         # output qty this BOM yields
    yield_percent = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    scrap_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_alternate = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="draft")    # draft|active|archived

    class Meta:
        db_table = "mfg_boms"
        indexes = [models.Index(fields=["workspace_id", "product_item_id", "status"])]


class BomComponent(TenantModel):
    bom_id = models.UUIDField(db_index=True)
    component_item_id = models.UUIDField(db_index=True)          # → Inventory Item
    quantity = models.DecimalField(**QTY)
    scrap_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    alternate_group = models.CharField(max_length=32, blank=True)
    sequence = models.IntegerField(default=10)

    class Meta:
        db_table = "mfg_bom_components"
        indexes = [models.Index(fields=["workspace_id", "bom_id", "sequence"])]


class Routing(TenantModel):
    number = models.CharField(max_length=64, blank=True)
    product_item_id = models.UUIDField(db_index=True)
    revision = models.CharField(max_length=20, default="A")
    status = models.CharField(max_length=20, default="active")

    class Meta:
        db_table = "mfg_routings"
        indexes = [models.Index(fields=["workspace_id", "product_item_id"])]


class RoutingStep(TenantModel):
    routing_id = models.UUIDField(db_index=True)
    sequence = models.IntegerField(default=10)
    work_center_id = models.UUIDField()
    setup_minutes = models.DecimalField(**QTY)
    run_minutes = models.DecimalField(**QTY)        # per unit
    queue_minutes = models.DecimalField(**QTY)
    move_minutes = models.DecimalField(**QTY)

    class Meta:
        db_table = "mfg_routing_steps"
        indexes = [models.Index(fields=["workspace_id", "routing_id", "sequence"])]


class ProductionOrder(TenantModel):
    number = models.CharField(max_length=64, blank=True)
    product_item_id = models.UUIDField(db_index=True)
    bom_id = models.UUIDField(null=True, blank=True)
    routing_id = models.UUIDField(null=True, blank=True)
    warehouse_id = models.UUIDField(null=True, blank=True)       # → Inventory Warehouse
    quantity = models.DecimalField(**QTY)
    priority = models.CharField(max_length=20, default="medium")
    status = models.CharField(max_length=20, default="draft")
    # draft|planned|released|in_progress|completed|closed|cancelled
    planned_start = models.DateField(null=True, blank=True)
    planned_finish = models.DateField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_finish = models.DateTimeField(null=True, blank=True)
    material_cost = models.DecimalField(**MONEY)
    labor_cost = models.DecimalField(**MONEY)
    overhead_cost = models.DecimalField(**MONEY)
    total_cost = models.DecimalField(**MONEY)
    good_qty = models.DecimalField(**QTY)
    scrap_qty = models.DecimalField(**QTY)
    journal_entry_id = models.UUIDField(null=True, blank=True)
    source_project_id = models.UUIDField(null=True, blank=True)  # ETO → Projects

    class Meta:
        db_table = "mfg_production_orders"
        indexes = [models.Index(fields=["workspace_id", "status", "product_item_id"])]


class ProductionOperation(TenantModel):
    production_order_id = models.UUIDField(db_index=True)
    routing_step_id = models.UUIDField(null=True, blank=True)
    work_center_id = models.UUIDField(null=True, blank=True)
    sequence = models.IntegerField(default=10)
    status = models.CharField(max_length=20, default="pending")  # pending|in_progress|paused|completed
    planned_start = models.DateField(null=True, blank=True)
    planned_finish = models.DateField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_finish = models.DateTimeField(null=True, blank=True)
    labor_minutes = models.DecimalField(**QTY)
    machine_minutes = models.DecimalField(**QTY)
    downtime_minutes = models.DecimalField(**QTY)
    downtime_reason = models.CharField(max_length=40, blank=True)
    good_qty = models.DecimalField(**QTY)
    reject_qty = models.DecimalField(**QTY)

    class Meta:
        db_table = "mfg_production_operations"
        indexes = [models.Index(fields=["workspace_id", "production_order_id", "sequence"])]


class MaterialReservation(TenantModel):
    production_order_id = models.UUIDField(db_index=True)
    component_item_id = models.UUIDField(db_index=True)
    required_qty = models.DecimalField(**QTY)
    reserved_qty = models.DecimalField(**QTY)
    issued_qty = models.DecimalField(**QTY)
    unit_cost = models.DecimalField(**MONEY)

    class Meta:
        db_table = "mfg_material_reservations"
        indexes = [models.Index(fields=["workspace_id", "production_order_id"])]


class ProductionCost(TenantModel):
    production_order_id = models.UUIDField(db_index=True)
    cost_type = models.CharField(max_length=20)   # material|labor|overhead|machine
    amount = models.DecimalField(**MONEY)
    reference = models.CharField(max_length=128, blank=True)

    class Meta:
        db_table = "mfg_production_costs"
        indexes = [models.Index(fields=["workspace_id", "production_order_id", "cost_type"])]


class QualityCheck(TenantModel):
    production_order_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=150)
    sampling_percent = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    sampled_qty = models.DecimalField(**QTY)
    passed_qty = models.DecimalField(**QTY)
    failed_qty = models.DecimalField(**QTY)
    result = models.CharField(max_length=20, default="pass")  # pass|fail|rework|scrap

    class Meta:
        db_table = "mfg_quality_checks"
        indexes = [models.Index(fields=["workspace_id", "production_order_id"])]


class NonConformance(TenantModel):
    production_order_id = models.UUIDField(null=True, blank=True)
    defect = models.CharField(max_length=255)
    root_cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    preventive_action = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="open")  # open|investigating|capa|closed

    class Meta:
        db_table = "mfg_non_conformances"
        indexes = [models.Index(fields=["workspace_id", "status"])]


class MRPRun(TenantModel):
    run_type = models.CharField(max_length=20, default="regenerative")  # regenerative|net_change
    status = models.CharField(max_length=20, default="completed")
    shortage_count = models.IntegerField(default=0)

    class Meta:
        db_table = "mfg_mrp_runs"


class MRPResult(TenantModel):
    mrp_run_id = models.UUIDField(db_index=True)
    item_id = models.UUIDField(db_index=True)
    demand = models.DecimalField(**QTY)
    available = models.DecimalField(**QTY)
    net_requirement = models.DecimalField(**QTY)
    suggested_qty = models.DecimalField(**QTY)
    action = models.CharField(max_length=20, default="none")  # manufacture|purchase|transfer|none

    class Meta:
        db_table = "mfg_mrp_results"
        indexes = [models.Index(fields=["workspace_id", "mrp_run_id"])]


class StockLot(TenantModel):
    """Lot/batch + serial traceability — links finished goods back to source material + supplier."""
    item_id = models.UUIDField(db_index=True)
    lot_number = models.CharField(max_length=64)
    batch_number = models.CharField(max_length=64, blank=True)
    serial_number = models.CharField(max_length=64, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    supplier_ref = models.CharField(max_length=128, blank=True)
    production_order_id = models.UUIDField(null=True, blank=True)
    consumed_lot_ids = models.JSONField(default=list)   # source lots (traceability chain)

    class Meta:
        db_table = "mfg_stock_lots"
        indexes = [models.Index(fields=["workspace_id", "item_id", "lot_number"])]
