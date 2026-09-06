"use client";

import { BomsPanel } from "@/components/manufacturing/boms-panel";
import { ManufacturingNav } from "@/components/manufacturing/manufacturing-nav";
import { StandardCostPanel } from "@/components/manufacturing/standard-cost-panel";
import { WorkCentersPanel } from "@/components/manufacturing/work-centers-panel";

export default function ManufacturingBomsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">BOMs &amp; work centers</h1>
        <p className="text-sm text-muted-foreground">
          Define work centers and bills of materials. Approve a BOM to use it for explosion and production.
        </p>
      </div>
      <ManufacturingNav />
      <WorkCentersPanel />
      <BomsPanel />
      <StandardCostPanel />
    </div>
  );
}
