"use client";

import Link from "next/link";

import { AccountingNav } from "@/components/accounting/accounting-nav";

const CARDS = [
  { href: "/accounting/journal", label: "Journal", description: "Post and reverse double-entry transactions." },
  { href: "/accounting/accounts", label: "Chart of accounts", description: "Asset, liability, equity, revenue, expense accounts." },
  { href: "/accounting/periods", label: "Periods", description: "Open, close, and lock posting windows." },
];

export default function AccountingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Accounting</h1>
        <p className="text-sm text-muted-foreground">
          Double-entry general ledger. Posted entries are immutable; corrections are made by reversal.
        </p>
      </div>
      <AccountingNav />
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
