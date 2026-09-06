"use client";

import { InventoryNav } from "@/components/inventory/inventory-nav";
import { WarehousesPanel } from "@/components/inventory/warehouses-panel";

export default function InventoryWarehousesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Warehouses</h1>
        <p className="text-sm text-muted-foreground">Stocking locations. Every movement is posted against a warehouse.</p>
      </div>
      <InventoryNav />
      <WarehousesPanel />
    </div>
  );
}
