"use client";

import { LineageGraphPanel } from "@/components/admin/lineage-graph";

export default function AdminLineagePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Data lineage</h1>
        <p className="text-sm text-muted-foreground">
          Trace what feeds a piece of data and what depends on it — for impact analysis.
        </p>
      </div>
      <LineageGraphPanel />
    </div>
  );
}
