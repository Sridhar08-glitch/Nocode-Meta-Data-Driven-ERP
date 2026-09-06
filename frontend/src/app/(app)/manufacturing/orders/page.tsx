"use client";

import { ManufacturingNav } from "@/components/manufacturing/manufacturing-nav";
import { OrdersPanel } from "@/components/manufacturing/orders-panel";

export default function ManufacturingOrdersPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Production orders</h1>
        <p className="text-sm text-muted-foreground">
          Create a manufacturing order, then drive its release → issue → complete → close lifecycle.
        </p>
      </div>
      <ManufacturingNav />
      <OrdersPanel />
    </div>
  );
}
