"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/payroll", label: "Overview", exact: true },
  { href: "/payroll/structures", label: "Salary structures" },
  { href: "/payroll/runs", label: "Periods & runs" },
  { href: "/payroll/payslips", label: "Payslips" },
  { href: "/payroll/loans", label: "Loans & inputs" },
];

/** Sub-navigation across the payroll engine pages. */
export function PayrollNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-1 border-b pb-2" aria-label="Payroll">
      {LINKS.map((l) => {
        const active = l.exact ? pathname === l.href : pathname.startsWith(l.href);
        return (
          <Link
            key={l.href}
            href={l.href}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm transition-colors",
              active
                ? "bg-primary/10 font-medium text-primary"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {l.label}
          </Link>
        );
      })}
    </nav>
  );
}
