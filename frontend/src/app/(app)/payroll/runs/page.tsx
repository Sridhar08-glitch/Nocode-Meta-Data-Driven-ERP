"use client";

import { PayrollNav } from "@/components/payroll/payroll-nav";
import { RunsPanel } from "@/components/payroll/runs-panel";

export default function PayrollRunsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Periods & runs</h1>
        <p className="text-sm text-muted-foreground">
          Open a pay period, create a run, then drive its lifecycle. Segregation of duties is enforced server-side.
        </p>
      </div>
      <PayrollNav />
      <RunsPanel />
    </div>
  );
}
