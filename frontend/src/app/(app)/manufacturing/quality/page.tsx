"use client";

import { ManufacturingNav } from "@/components/manufacturing/manufacturing-nav";
import { QualityPanel } from "@/components/manufacturing/quality-panel";

export default function ManufacturingQualityPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Quality &amp; traceability</h1>
        <p className="text-sm text-muted-foreground">
          Record quality checks and non-conformances, and trace finished lots back to their inputs.
        </p>
      </div>
      <ManufacturingNav />
      <QualityPanel />
    </div>
  );
}
