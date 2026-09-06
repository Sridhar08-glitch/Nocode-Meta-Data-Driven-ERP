"use client";

import { BusinessCalendarBuilder } from "@/components/sla/business-calendar-builder";
import { SlaSimulationPanel } from "@/components/sla/sla-simulation-panel";

export default function CalendarsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Business calendars</h1>
        <p className="text-sm text-muted-foreground">
          Working hours and holidays used by business-hours SLA targets.
        </p>
      </div>
      <BusinessCalendarBuilder />
      <SlaSimulationPanel />
    </div>
  );
}
