"use client";

import { AnalyticsNav } from "@/components/analytics/analytics-nav";
import { KpiRegistry } from "@/components/analytics/kpi-registry";

export default function AnalyticsKpisPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">KPI registry</h1>
        <p className="text-sm text-muted-foreground">
          The catalog of KPIs. Each is sourced from an NQL query (with an aggregate over a value
          field) or a server-resolved native key, and graded against its target and thresholds.
        </p>
      </div>
      <AnalyticsNav />
      <KpiRegistry />
    </div>
  );
}
