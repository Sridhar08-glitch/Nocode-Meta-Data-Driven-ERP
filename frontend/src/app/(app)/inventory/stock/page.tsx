"use client";

import { InventoryNav } from "@/components/inventory/inventory-nav";
import { StockBalance } from "@/components/inventory/stock-balance";

export default function InventoryStockPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Stock & valuation</h1>
        <p className="text-sm text-muted-foreground">On-hand balances and total inventory value, computed from the cost ledger.</p>
      </div>
      <InventoryNav />
      <StockBalance />
    </div>
  );
}
