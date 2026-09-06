"use client";

import Link from "next/link";

import { InventoryNav } from "@/components/inventory/inventory-nav";

const CARDS = [
  { href: "/inventory/items", label: "Items", description: "Stock items with SKU, unit, and costing method." },
  { href: "/inventory/warehouses", label: "Warehouses", description: "Stocking locations that hold per-item balances." },
  { href: "/inventory/stock", label: "Stock & valuation", description: "On-hand quantity, average cost, and total value." },
  { href: "/inventory/transactions", label: "Transactions", description: "Receive, issue, adjust, and transfer stock." },
  { href: "/inventory/movements", label: "Movements", description: "Immutable ledger of every stock change." },
];

export default function InventoryPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Inventory</h1>
        <p className="text-sm text-muted-foreground">
          Perpetual inventory with FIFO and weighted-average costing. Stock math is race-safe and the movement ledger is immutable.
        </p>
      </div>
      <InventoryNav />
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((c) => (
          <li key={c.href}>
            <Link href={c.href} className="flex h-full flex-col gap-1 rounded-lg border p-4 transition-colors hover:bg-accent">
              <span className="font-medium">{c.label}</span>
              <span className="text-xs text-muted-foreground">{c.description}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
