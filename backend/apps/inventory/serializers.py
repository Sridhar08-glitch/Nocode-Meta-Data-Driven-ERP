"""DRF serializers for the Inventory Engine API (Phase P2.4)."""
from rest_framework import serializers

from .models import Item, ItemCategory, Location, StockMovement, Warehouse


class ItemCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemCategory
        fields = ["id", "name", "parent", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "sku", "name", "category", "uom", "valuation_method", "standard_cost",
                  "track_inventory", "is_active", "inventory_account_code", "cogs_account_code",
                  "description", "created_by", "created_at", "updated_at"]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "code", "name", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "warehouse", "code", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class StockMovementSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source="item.sku", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = StockMovement
        fields = ["id", "item", "sku", "warehouse", "warehouse_code", "location", "movement_type",
                  "quantity", "unit_cost", "total_cost", "on_hand_after", "occurred_at",
                  "reference", "memo", "journal_entry_id", "created_at"]
        read_only_fields = fields
