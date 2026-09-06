"use client";

import { FinancialsPanel } from "@/components/projects/financials-panel";
import { ProjectsNav } from "@/components/projects/projects-nav";

export default function ProjectsFinancialsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Financials</h1>
        <p className="text-sm text-muted-foreground">
          Budget, profitability, and earned-value (EVM) for a project. Post cost entries (payroll,
          procurement, asset, expense, timesheet) and roll them up onto the project. All financial math
          runs server-side.
        </p>
      </div>
      <ProjectsNav />
      <FinancialsPanel />
    </div>
  );
}
