"use client";

import Link from "next/link";

import { AnalyticsNav } from "@/components/analytics/analytics-nav";
import { ScorecardView } from "@/components/analytics/scorecard-view";

const CARDS = [
  { href: "/analytics/kpis", label: "KPI registry", description: "Define KPIs (NQL or native) with targets, thresholds and direction." },
  { href: "/analytics/scorecards", label: "Scorecards", description: "Every executive role's scorecard (CEO/CFO/COO/CHRO/CIO)." },
  { href: "/analytics/health", label: "ERP health", description: "All KPIs evaluated and graded, grouped by module category." },
];

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground">
          Native analytics &amp; KPI registry. KPI evaluation, grading against thresholds, and
          time-series snapshots run server-side; pick an executive role to see its scorecard.
        </p>
      </div>
      <AnalyticsNav />
      <ScorecardView />
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((c) => (
          <li key={c.href}>
            <Link href={c.href} className="flex h-full flex-col gap-1 rounded-lg border p-4 transition-colors hover:bg-accent">
              <span className="font-medium">{c.label}</span>
              <span className="text-xs text-muted-foreground">{c.description}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
