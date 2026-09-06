"use client";

import { RecycleBin } from "@/components/admin/recycle-bin";

export default function AdminRecycleBinPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Recycle bin</h1>
        <p className="text-sm text-muted-foreground">
          Restore soft-deleted records before they auto-purge, or purge them permanently.
        </p>
      </div>
      <RecycleBin />
    </div>
  );
}
