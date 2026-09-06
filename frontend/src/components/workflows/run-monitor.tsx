"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { RunStatus } from "@/lib/workflows/api";
import {
  useCancelRun,
  useRetryRun,
  useWorkflowRun,
  useWorkflowRuns,
} from "@/lib/workflows/hooks";

const RUN_VARIANT: Record<RunStatus, "default" | "secondary" | "outline" | "destructive"> = {
  completed: "default",
  running: "secondary",
  queued: "outline",
  cancelled: "outline",
  failed: "destructive",
  timed_out: "destructive",
};

/** Run + instance monitor (Phase F1.10): run list → expandable step logs, cancel/retry. */
export function RunMonitor({ definitionId }: { definitionId: string }) {
  const runs = useWorkflowRuns({ workflow_id: definitionId });
  const [openRun, setOpenRun] = useState<string | null>(null);

  if (runs.isLoading) return <Skeleton className="h-48 w-full" />;
  if (runs.isError) return <ErrorState title="Couldn't load runs" />;
  const rows = runs.data?.results ?? [];
  if (rows.length === 0) {
    return <EmptyState title="No runs yet" description="This workflow hasn't run." />;
  }

  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.id} className="rounded-md border">
          <div className="flex items-center justify-between gap-2 p-3 text-sm">
            <button
              className="flex items-center gap-2 hover:underline"
              onClick={() => setOpenRun((cur) => (cur === r.id ? null : r.id))}
              aria-expanded={openRun === r.id}
            >
              <Badge variant={RUN_VARIANT[r.status]}>{r.status}</Badge>
              <span className="font-mono text-xs text-muted-foreground">{r.id.slice(0, 8)}</span>
              {r.duration_ms != null && (
                <span className="text-xs text-muted-foreground">{r.duration_ms} ms</span>
              )}
            </button>
            <RunActions run={r} />
          </div>
          {openRun === r.id && <RunSteps runId={r.id} />}
        </li>
      ))}
    </ul>
  );
}

function RunActions({ run }: { run: { id: string; status: RunStatus } }) {
  const cancel = useCancelRun();
  const retry = useRetryRun();
  const cancellable = run.status === "running" || run.status === "queued";
  const retryable = run.status === "failed" || run.status === "cancelled" || run.status === "timed_out";

  async function act(kind: "cancel" | "retry") {
    try {
      if (kind === "cancel") await cancel.mutateAsync(run.id);
      else await retry.mutateAsync(run.id);
      toast.success(kind === "cancel" ? "Run cancelled" : "Run retried");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    }
  }

  return (
    <span className="flex gap-1">
      {cancellable && (
        <Button variant="ghost" size="sm" onClick={() => act("cancel")} disabled={cancel.isPending}>
          Cancel
        </Button>
      )}
      {retryable && (
        <Button variant="ghost" size="sm" onClick={() => act("retry")} disabled={retry.isPending}>
          Retry
        </Button>
      )}
    </span>
  );
}

function RunSteps({ runId }: { runId: string }) {
  const detail = useWorkflowRun(runId);
  if (detail.isLoading) return <Skeleton className="m-3 h-20" />;
  if (detail.isError || !detail.data) return <ErrorState className="m-3 border-0" title="Couldn't load steps" />;
  const stepRuns = detail.data.step_runs ?? [];

  return (
    <div className="border-t border-border p-3">
      {detail.data.error_message && (
        <p className="mb-2 text-xs text-destructive">{detail.data.error_message}</p>
      )}
      {stepRuns.length === 0 ? (
        <p className="text-xs text-muted-foreground">No step logs.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {stepRuns.map((sr) => (
            <li key={sr.id} className="flex items-center gap-2">
              <Badge variant={sr.status === "failed" ? "destructive" : "outline"}>{sr.status}</Badge>
              <span className="font-mono text-xs text-muted-foreground">{sr.step_id.slice(0, 8)}</span>
              {sr.error_message && <span className="text-xs text-destructive">{sr.error_message}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
