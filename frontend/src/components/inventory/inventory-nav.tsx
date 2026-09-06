"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/inventory", label: "Overview", exact: true },
  { href: "/inventory/items", label: "Items" },
  { href: "/inventory/warehouses", label: "Warehouses" },
  { href: "/inventory/stock", label: "Stock & valuation" },
  { href: "/inventory/transactions", label: "Transactions" },
  { href: "/inventory/movements", label: "Movements" },
];

/** Sub-navigation across the inventory module pages. */
export function InventoryNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-1 border-b pb-2" aria-label="Inventory">
      {LINKS.map((l) => {
        const active = l.exact ? pathname === l.href : pathname.startsWith(l.href);
        return (
          <Link key={l.href} href={l.href}
            className={cn("rounded-md px-3 py-1.5 text-sm transition-colors",
              active ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
