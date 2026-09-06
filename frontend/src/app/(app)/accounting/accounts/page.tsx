"use client";

import { AccountingNav } from "@/components/accounting/accounting-nav";
import { ChartOfAccounts } from "@/components/accounting/chart-of-accounts";

export default function AccountsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Chart of accounts</h1>
        <p className="text-sm text-muted-foreground">Accounts grouped by type.</p>
      </div>
      <AccountingNav />
      <ChartOfAccounts />
    </div>
  );
}
