"use client";

import { AccountingNav } from "@/components/accounting/accounting-nav";
import { FinancialReports } from "@/components/accounting/financial-reports";

export default function ReportsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Financial reports</h1>
        <p className="text-sm text-muted-foreground">
          Trial balance, profit &amp; loss, balance sheet, and general ledger — derived live from posted entries.
        </p>
      </div>
      <AccountingNav />
      <FinancialReports />
    </div>
  );
}
