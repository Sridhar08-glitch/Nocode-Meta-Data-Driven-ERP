"use client";

import { SlaBuilder } from "@/components/sla/sla-builder";

export default function SlaPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">SLAs</h1>
        <p className="text-sm text-muted-foreground">Response/resolution targets with business-hours awareness.</p>
      </div>
      <SlaBuilder />
    </div>
  );
}
