"use client";

import { HrOverview } from "@/components/hr/hr-overview";

/**
 * HR Solution overview (Phase P2.7). The generic metadata runtime renders the org/recruitment/people/
 * time/performance/lifecycle entity CRUD; this page exposes the HR lifecycle actions that runtime
 * can't express (hire a candidate, complete an interview, accept an offer, approve/reject leave,
 * complete a review, promote/transfer/offboard an employee).
 */
export default function HrPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">HR</h1>
        <p className="text-sm text-muted-foreground">
          Hire-to-retire people operations: org structure, recruitment, employees, time &amp; leave,
          performance, and lifecycle changes. Hiring a candidate creates a numbered employee; promotions
          and transfers move people across the org.
        </p>
      </div>
      <HrOverview />
    </div>
  );
}
