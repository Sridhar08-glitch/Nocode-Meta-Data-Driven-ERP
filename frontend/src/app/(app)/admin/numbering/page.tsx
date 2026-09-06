"use client";

import { NumberingManager } from "@/components/admin/numbering-manager";

export default function NumberingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Numbering</h1>
        <p className="text-sm text-muted-foreground">
          Gapless, concurrency-safe document number sequences (invoices, POs, journal entries, …).
          Finance modules auto-register their own; you can add custom ones here.
        </p>
      </div>
      <NumberingManager />
    </div>
  );
}
