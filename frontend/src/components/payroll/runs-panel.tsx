"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { PayrollRun } from "@/lib/payroll/api";
import { useCanManagePayroll, useCreateRun, useRuns } from "@/lib/payroll/hooks";

import { PeriodsPanel } from "./periods-panel";
import { RunLifecycle } from "./run-lifecycle";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "success" | "destructive"> = {
  draft: "secondary",
  processing: "default",
  completed: "default",
  approved: "success",
  posted: "success",
  cancelled: "destructive",
  locked: "destructive",
};

/** Periods & runs (Phase P2.8) — pick a period, create/select a run, then drive its lifecycle. */
export function RunsPanel() {
  const [periodId, setPeriodId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <div className="space-y-6">
        <PeriodsPanel
          selectedId={periodId}
          onSelect={(id) => {
            setPeriodId(id);
            setRunId(null);
          }}
        />
        {periodId && <RunsForPeriod periodId={periodId} selectedRunId={runId} onSelectRun={setRunId} />}
      </div>
      <div>
        {runId ? (
          <RunLifecycle runId={runId} />
        ) : (
          <EmptyState
            title="No run selected"
            description="Select a pay period, then create or pick a run to drive its lifecycle."
          />
        )}
      </div>
    </div>
  );
}

function RunsForPeriod({
  periodId,
  selectedRunId,
  onSelectRun,
}: {
  periodId: string;
  selectedRunId: string | null;
  onSelectRun: (id: string) => void;
}) {
  const runs = useRuns({ payroll_period_id: periodId });
  const createRun = useCreateRun();
  const canManage = useCanManagePayroll();

  const rows = runs.data ?? [];

  async function create() {
    try {
      const run: PayrollRun = await createRun.mutateAsync(periodId);
      toast.success("Run created");
      onSelectRun(run.id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create run");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Runs</h2>
        {canManage && (
          <Button size="sm" onClick={create} disabled={createRun.isPending}>
            {createRun.isPending ? "Creating…" : "New run"}
          </Button>
        )}
      </div>
      {runs.isLoading ? (
        <Skeleton className="h-24 w-full" />
      ) : rows.length === 0 ? (
        <EmptyState title="No runs" description="Create a run for this period." />
      ) : (
        <ul className="space-y-1">
          {rows.map((run) => (
            <li key={run.id}>
              <button
                type="button"
                onClick={() => onSelectRun(run.id)}
                className={`flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-accent ${
                  run.id === selectedRunId ? "border-primary bg-primary/5" : ""
                }`}
              >
                <span className="flex items-center gap-2">
                  <span className="font-mono text-xs">{run.id.slice(0, 8)}</span>
                  <Badge variant={STATUS_VARIANT[run.status] ?? "secondary"}>{run.status}</Badge>
                </span>
                <span className="font-mono text-muted-foreground">{run.total_net}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
