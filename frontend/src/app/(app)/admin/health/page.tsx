"use client";

import { SlaHealth } from "@/components/admin/sla-health";
import { SystemStatus } from "@/components/admin/system-status";
import { TenantHealthPanel } from "@/components/admin/tenant-health";

export default function AdminHealthPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Tenant health</h1>
        <p className="text-sm text-muted-foreground">
          Workflow, activity, record, error, storage, and SLA KPIs for the workspace.
        </p>
      </div>
      <SystemStatus />
      <TenantHealthPanel />
      <SlaHealth />
    </div>
  );
}
