"use client";

import { HelpdeskNav } from "@/components/helpdesk/helpdesk-nav";
import { SlaPanel } from "@/components/helpdesk/sla-panel";

export default function HelpdeskSlaPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">SLA dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Workspace SLA health for helpdesk tickets — breached, warning, on-track, met, and paused counts.
          This reuses the SLA engine; all counts are computed server-side.
        </p>
      </div>
      <HelpdeskNav />
      <SlaPanel />
    </div>
  );
}
