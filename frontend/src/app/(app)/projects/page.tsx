"use client";

import { ProjectsNav } from "@/components/projects/projects-nav";
import { ProjectsOverview } from "@/components/projects/projects-overview";

/**
 * Project Management + PSA overview (Phase P2.10). HYBRID solution: the generic metadata runtime
 * renders the portfolio/program/project delivery, work, people, and governance entity CRUD; this page
 * ties them together with module-grouped links, the native financials/schedule/resources engines, and
 * the project lifecycle actions (start/complete/baseline, approve budget, complete task/milestone,
 * approve timesheet/expense/change-request/deliverable) that runtime can't express.
 */
export default function ProjectsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Project Management</h1>
        <p className="text-sm text-muted-foreground">
          Professional services automation: portfolios, programs &amp; projects, work &amp; sprints,
          people &amp; timesheets, and governance, plus the native cost-rollup, financials (EVM),
          scheduling, and resourcing engines. Project documents are rendered by the generic record
          runtime; lifecycle, financials, schedule, and resourcing are driven here.
        </p>
      </div>
      <ProjectsNav />
      <ProjectsOverview />
    </div>
  );
}
