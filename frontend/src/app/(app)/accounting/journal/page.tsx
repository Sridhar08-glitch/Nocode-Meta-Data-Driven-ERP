"use client";

import { AccountingNav } from "@/components/accounting/accounting-nav";
import { JournalEntries } from "@/components/accounting/journal-entries";

export default function JournalPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Journal</h1>
        <p className="text-sm text-muted-foreground">Balanced double-entry transactions.</p>
      </div>
      <AccountingNav />
      <JournalEntries />
    </div>
  );
}
