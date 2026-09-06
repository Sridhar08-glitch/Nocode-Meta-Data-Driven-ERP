"use client";

import { AccountingNav } from "@/components/accounting/accounting-nav";
import { AccountingPeriods } from "@/components/accounting/accounting-periods";

export default function PeriodsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Periods</h1>
        <p className="text-sm text-muted-foreground">Open, close, and lock posting windows.</p>
      </div>
      <AccountingNav />
      <AccountingPeriods />
    </div>
  );
}
