"use client";

import Link from "next/link";

import { ManufacturingNav } from "@/components/manufacturing/manufacturing-nav";
import { ManufacturingOverview } from "@/components/manufacturing/manufacturing-overview";

const CARDS = [
  { href: "/manufacturing/boms", label: "BOMs & work centers", description: "Define work centers and bills of materials, then approve them." },
  { href: "/manufacturing/orders", label: "Production orders", description: "Release → issue → complete → close, with operations and OEE." },
  { href: "/manufacturing/mrp", label: "MRP", description: "Net-requirement planning: manufacture vs purchase suggestions." },
  { href: "/manufacturing/quality", label: "Quality & traceability", description: "Quality checks, NCRs, and finished-lot traceability." },
];

export default function ManufacturingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Manufacturing</h1>
        <p className="text-sm text-muted-foreground">
          Native manufacturing &amp; MRP engine. BOM explosion, inventory consumption to WIP, GL posting,
          cost rollup, OEE and MRP netting run server-side.
        </p>
      </div>
      <ManufacturingNav />
      <ManufacturingOverview />
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
