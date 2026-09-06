"use client";

import { ManufacturingNav } from "@/components/manufacturing/manufacturing-nav";
import { MrpPanel } from "@/components/manufacturing/mrp-panel";

export default function ManufacturingMrpPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">MRP</h1>
        <p className="text-sm text-muted-foreground">
          Material requirements planning. Enter demand and read back per-item net requirements and suggested actions.
        </p>
      </div>
      <ManufacturingNav />
      <MrpPanel />
    </div>
  );
}
