"use client";

import { AssetsNav } from "@/components/assets/assets-nav";
import { DisposalPanel } from "@/components/assets/disposal-panel";

export default function AssetsDisposalsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Disposals</h1>
        <p className="text-sm text-muted-foreground">
          Record an asset disposal (sale, scrap, donation, or write-off). The gain or loss versus net
          book value is computed server-side.
        </p>
      </div>
      <AssetsNav />
      <DisposalPanel />
    </div>
  );
}
