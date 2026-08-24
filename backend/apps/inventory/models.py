"""
Inventory Engine (Phase P2.4) — master data + a transactional stock ledger with FIFO / weighted-
average valuation. Stock math is integrity-critical: quantities and costs are mutated only under a
``SELECT … FOR UPDATE`` lock on the ``StockLevel`` row, so concurrent movements can never race.
Every movement is recorded immutably in ``StockMovement`` (the inventory ledger) and can post to
the GL via the P2.2 posting bus.

All tables are workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

FIFO = "fifo"
AVERAGE = "average"
STANDARD = "standard"
VALUATION_METHODS = [(FIFO, "FIFO"), (AVERAGE, "Weighted average"), (STANDARD, "Standard cost")]

# Movement types — sign of the quantity effect is derived in the service, not stored as a guess.
RECEIPT = "receipt"
ISSUE = "issue"
ADJUSTMENT = "adjustment"
TRANSFER_IN = "transfer_in"
TRANSFER_OUT = "transfer_out"
MOVEMENT_TYPES = [
    (RECEIPT, "Receipt"),
    (ISSUE, "Issue"),
    (ADJUSTMENT, "Adjustment"),
    (TRANSFER_IN, "Transfer in"),
    (TRANSFER_OUT, "Transfer out"),
]


class ItemCategory(TenantModel):
    name = models.CharField(max_length=150)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    description = models.TextField(blank=True)

    class Meta:
        db_table = "inv_item_categories"
        indexes = [models.Index(fields=["workspace_id", "name"])]

    def __str__(self):
        return self.name


class Item(TenantModel):
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(ItemCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="items")
    uom = models.CharField(max_length=20, default="ea")           # unit of measure
    valuation_method = models.CharField(max_length=10, choices=VALUATION_METHODS, default=AVERAGE)
    standard_cost = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    track_inventory = models.BooleanField(default=True)           # services vs stocked goods
    is_active = models.BooleanField(default=True)
    # Optional GL account codes for the posting bus (resolved by PostingRule context).
    inventory_account_code = models.CharField(max_length=32, blank=True)
    cogs_account_code = models.CharField(max_length=32, blank=True)
    description = models.TextField(blank=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "inv_items"
        unique_together = [("workspace_id", "sku")]
        indexes = [models.Index(fields=["workspace_id", "sku"]),
                   models.Index(fields=["workspace_id", "name"])]

    def __str__(self):
        return f"{self.sku} {self.name}"


class Warehouse(TenantModel):
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "inv_warehouses"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "code"])]

    def __str__(self):
        return f"{self.code} {self.name}"


class Location(TenantModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="locations")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=150, blank=True)

    class Meta:
        db_table = "inv_locations"
        unique_together = [("workspace_id", "warehouse", "code")]
        indexes = [models.Index(fields=["workspace_id", "warehouse"])]

    def __str__(self):
        return f"{self.warehouse_id}/{self.code}"


class StockLevel(TenantModel):
    """Running balance of an item in a warehouse. Mutated only under a row lock (the race-safe
    point of truth). ``avg_cost`` is maintained for weighted-average items; FIFO items derive
    value from ``FIFOLayer`` rows."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="stock_levels")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="stock_levels")
    on_hand = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    avg_cost = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    value = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    class Meta:
        db_table = "inv_stock_levels"
        unique_together = [("workspace_id", "item", "warehouse")]
        indexes = [models.Index(fields=["workspace_id", "item", "warehouse"])]

    def __str__(self):
        return f"{self.item_id}@{self.warehouse_id}={self.on_hand}"


class FIFOLayer(TenantModel):
    """A cost layer for FIFO-valued items: each receipt opens a layer; issues consume the oldest
    open layers first. ``remaining`` decrements to zero as the layer is depleted."""

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="fifo_layers")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="fifo_layers")
    received_at = models.DateTimeField()
    original_qty = models.DecimalField(max_digits=20, decimal_places=4)
    remaining = models.DecimalField(max_digits=20, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=20, decimal_places=4)

    class Meta:
        db_table = "inv_fifo_layers"
        indexes = [models.Index(fields=["workspace_id", "item", "warehouse", "received_at"])]

    def __str__(self):
        return f"layer {self.item_id} {self.remaining}@{self.unit_cost}"


class StockMovement(TenantModel):
    """Immutable inventory ledger row — one per stock event. ``quantity`` is signed (+in / −out);
    ``on_hand_after`` snapshots the running balance for audit/trace."""

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="movements")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="movements")
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name="movements")
    movement_type = models.CharField(max_length=12, choices=MOVEMENT_TYPES)
    quantity = models.DecimalField(max_digits=20, decimal_places=4)        # signed
    unit_cost = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    total_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    on_hand_after = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    occurred_at = models.DateTimeField()
    reference = models.CharField(max_length=128, blank=True)               # PO/SO/doc number
    memo = models.CharField(max_length=300, blank=True)
    journal_entry_id = models.UUIDField(null=True, blank=True)             # GL link if posted
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "inv_stock_movements"
        indexes = [
            models.Index(fields=["workspace_id", "item", "warehouse", "occurred_at"]),
            models.Index(fields=["workspace_id", "movement_type"]),
        ]

    def __str__(self):
        return f"{self.movement_type} {self.quantity} {self.item_id}"
