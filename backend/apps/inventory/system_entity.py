"""
Inventory → System-Entity descriptors (B0). Second consumer proving the adapter is GENERIC (not
finance-specific): the same registry renders inventory native models through the Generic Runtime.
Item/Warehouse are createable via a thin reuse of their models; stock levels + movements are read-only
(movements are an immutable ledger). Registered at `InventoryConfig.ready()`.
"""
from __future__ import annotations

from apps.system_entities.registry import SystemEntity, register

from .models import Item, StockLevel, StockMovement, Warehouse


def _item_create(*, workspace_id, data, actor_id=None):
    return Item.objects.create(
        workspace_id=workspace_id, sku=data.get("sku", ""), name=data.get("name", ""),
        uom=data.get("uom", "ea"), valuation_method=data.get("valuation_method", "average"),
        standard_cost=data.get("standard_cost", 0) or 0,
        track_inventory=bool(data.get("track_inventory", True)),
        description=data.get("description", ""), created_by=actor_id)


def _warehouse_create(*, workspace_id, data, actor_id=None):
    return Warehouse.objects.create(
        workspace_id=workspace_id, code=data.get("code", ""), name=data.get("name", ""))


def register_system_entities() -> None:
    register(SystemEntity(
        slug="inventory_item", model=Item, name="Item", plural_name="Items", module="inventory",
        can_create=True, create_fn=_item_create, default_ordering="sku"))
    register(SystemEntity(
        slug="inventory_warehouse", model=Warehouse, name="Warehouse", plural_name="Warehouses",
        module="inventory", can_create=True, create_fn=_warehouse_create, default_ordering="code"))
    register(SystemEntity(
        slug="inventory_stock_level", model=StockLevel, name="Stock Level",
        plural_name="Stock Levels", module="inventory", default_ordering="-value"))
    register(SystemEntity(
        slug="inventory_movement", model=StockMovement, name="Stock Movement",
        plural_name="Stock Movements", module="inventory", default_ordering="-created_at"))
