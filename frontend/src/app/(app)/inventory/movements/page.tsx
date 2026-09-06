"use client";

import { InventoryNav } from "@/components/inventory/inventory-nav";
import { MovementHistory } from "@/components/inventory/movement-history";

export default function InventoryMovementsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Movements</h1>
        <p className="text-sm text-muted-foreground">Immutable, append-only ledger of every stock change.</p>
      </div>
      <InventoryNav />
      <MovementHistory />
    </div>
  );
}
