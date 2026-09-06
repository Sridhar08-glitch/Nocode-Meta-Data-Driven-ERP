"use client";

import { MarketplaceStore } from "@/components/admin/marketplace-store";

export default function AdminMarketplacePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Marketplace</h1>
        <p className="text-sm text-muted-foreground">
          Browse and install plugins, then manage upgrades, rollbacks, and uninstalls.
        </p>
      </div>
      <MarketplaceStore />
    </div>
  );
}
