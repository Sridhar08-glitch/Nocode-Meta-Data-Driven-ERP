"use client";

import { InventoryNav } from "@/components/inventory/inventory-nav";
import { ItemsPanel } from "@/components/inventory/items-panel";

export default function InventoryItemsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Items</h1>
        <p className="text-sm text-muted-foreground">Stock items. Costing method is fixed once movements exist.</p>
      </div>
      <InventoryNav />
      <ItemsPanel />
    </div>
  );
}
