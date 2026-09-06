"use client";

import { BackupsPanel } from "@/components/admin/backups";

export default function AdminBackupsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Backups &amp; restore</h1>
        <p className="text-sm text-muted-foreground">
          Create backups and restore point-in-time into an isolated target workspace.
        </p>
      </div>
      <BackupsPanel />
    </div>
  );
}
