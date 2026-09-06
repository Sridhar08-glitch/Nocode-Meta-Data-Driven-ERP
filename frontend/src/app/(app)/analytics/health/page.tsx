"use client";

import { AnalyticsNav } from "@/components/analytics/analytics-nav";
import { HealthGrid } from "@/components/analytics/health-grid";

export default function AnalyticsHealthPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">ERP health</h1>
        <p className="text-sm text-muted-foreground">
          Every KPI evaluated and graded, grouped by module category — a module-by-module health
          grid across the ERP.
        </p>
      </div>
      <AnalyticsNav />
      <HealthGrid />
    </div>
  );
}
