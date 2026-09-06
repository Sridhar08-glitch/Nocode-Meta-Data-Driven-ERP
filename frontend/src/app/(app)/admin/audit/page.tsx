"use client";

import { AuditExplorer } from "@/components/admin/audit-explorer";

export default function AdminAuditPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Audit log</h1>
        <p className="text-sm text-muted-foreground">
          Immutable, filterable event history for the workspace (owner/admin only).
        </p>
      </div>
      <AuditExplorer />
    </div>
  );
}
