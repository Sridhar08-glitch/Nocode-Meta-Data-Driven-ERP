"use client";

import { InventoryNav } from "@/components/inventory/inventory-nav";
import { TransactionsPanel } from "@/components/inventory/transactions-panel";

export default function InventoryTransactionsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Transactions</h1>
        <p className="text-sm text-muted-foreground">Post receive, issue, adjust, and transfer movements. Costing is applied server-side.</p>
      </div>
      <InventoryNav />
      <TransactionsPanel />
    </div>
  );
}
