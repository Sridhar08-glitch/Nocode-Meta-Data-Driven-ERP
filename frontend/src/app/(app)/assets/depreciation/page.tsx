"use client";

import { AssetsNav } from "@/components/assets/assets-nav";
import { DepreciationPanel } from "@/components/assets/depreciation-panel";

export default function AssetsDepreciationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Depreciation</h1>
        <p className="text-sm text-muted-foreground">
          Create depreciation schedules, post immutable period runs, and preview a full schedule
          without writing. All depreciation math runs server-side.
        </p>
      </div>
      <AssetsNav />
      <DepreciationPanel />
    </div>
  );
}
