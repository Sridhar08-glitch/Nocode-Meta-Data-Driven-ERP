"use client";

import { ConfigVcsPanel } from "@/components/admin/config-vcs";

export default function AdminConfigVcsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Configuration history</h1>
        <p className="text-sm text-muted-foreground">
          Commit the live workspace configuration, compare any two commits, and roll back.
        </p>
      </div>
      <ConfigVcsPanel />
    </div>
  );
}
