"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/accounting", label: "Overview", exact: true },
  { href: "/accounting/journal", label: "Journal" },
  { href: "/accounting/accounts", label: "Chart of accounts" },
  { href: "/accounting/periods", label: "Periods" },
  { href: "/accounting/reports", label: "Reports" },
];

/** Sub-navigation across the accounting module pages. */
export function AccountingNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-1 border-b pb-2" aria-label="Accounting">
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
