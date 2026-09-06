"use client";

import { AnalyticsNav } from "@/components/analytics/analytics-nav";
import { AllScorecards } from "@/components/analytics/scorecard-view";

export default function AnalyticsScorecardsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Executive scorecards</h1>
        <p className="text-sm text-muted-foreground">
          Every executive role&apos;s scorecard — each KPI graded good / warning / critical against
          its target and thresholds.
        </p>
      </div>
      <AnalyticsNav />
      <AllScorecards />
    </div>
  );
}
