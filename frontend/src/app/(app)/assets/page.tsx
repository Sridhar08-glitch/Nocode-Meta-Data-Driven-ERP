"use client";

import { AssetsNav } from "@/components/assets/assets-nav";
import { AssetsOverview } from "@/components/assets/assets-overview";

/**
 * Asset Management (EAM) overview (Phase P2.9). HYBRID solution: the generic metadata runtime renders
 * the asset registry/operations/maintenance/records entity CRUD; this page ties them together with
 * module-grouped links, the native depreciation/disposal engines, and the asset lifecycle actions
 * (assign/return/transfer/inspect/retire, complete a work order) that runtime can't express.
 */
export default function AssetsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Asset Management</h1>
        <p className="text-sm text-muted-foreground">
          Enterprise asset management: registry, assignments &amp; transfers, maintenance, and records,
          plus the native depreciation and disposal engines. Asset master data is rendered by the
          generic record runtime; lifecycle, depreciation, and disposal are driven here.
        </p>
      </div>
      <AssetsNav />
      <AssetsOverview />
    </div>
  );
}
