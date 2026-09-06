"use client";

import Link from "next/link";

import { PayrollNav } from "@/components/payroll/payroll-nav";
import { PayrollOverview } from "@/components/payroll/payroll-overview";

const CARDS = [
  { href: "/payroll/structures", label: "Salary structures", description: "Earning/deduction components used to compute pay." },
  { href: "/payroll/runs", label: "Periods & runs", description: "Open periods, then calculate → approve → post → lock runs." },
  { href: "/payroll/payslips", label: "Payslips", description: "Immutable payslips with a line-level breakdown." },
  { href: "/payroll/loans", label: "Loans & inputs", description: "Loans, advances, overtime and one-time adjustments." },
];

export default function PayrollPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Payroll</h1>
        <p className="text-sm text-muted-foreground">
          Native payroll engine. Component calculation, taxes, GL posting and segregation of duties run server-side; payslips are immutable once posted.
        </p>
      </div>
      <PayrollNav />
      <PayrollOverview />
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
