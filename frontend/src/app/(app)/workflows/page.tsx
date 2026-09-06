"use client";

import { useRouter } from "next/navigation";

import { WorkflowCreateDialog } from "@/components/workflows/workflow-create-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { WorkflowStatus } from "@/lib/workflows/api";
import {
  useDeleteWorkflow,
  useDuplicateWorkflow,
  useSetWorkflowStatus,
  useWorkflowDefinitions,
} from "@/lib/workflows/hooks";

const STATUS_VARIANT: Record<WorkflowStatus, "default" | "secondary" | "outline" | "destructive"> = {
  active: "default",
  paused: "secondary",
  draft: "outline",
  archived: "destructive",
};

export default function WorkflowsPage() {
  const router = useRouter();
  const defs = useWorkflowDefinitions();
  const setStatus = useSetWorkflowStatus();
  const duplicate = useDuplicateWorkflow();
  const del = useDeleteWorkflow();

  const rows = defs.data?.results ?? [];

  async function run(p: Promise<unknown>, ok: string) {
    try {
      await p;
      toast.success(ok);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Workflows</h1>
          <p className="text-sm text-muted-foreground">Automate actions when records change.</p>
        </div>
        <WorkflowCreateDialog onCreated={(id) => router.push(`/workflows/${id}`)} />
      </div>

      {defs.isLoading && <Skeleton className="h-64 w-full" />}
      {defs.isError && <ErrorState title="Couldn't load workflows" />}
      {defs.data && rows.length === 0 && (
        <EmptyState title="No workflows yet" description="Create your first automation." />
      )}

      {rows.length > 0 && (
        <ul className="space-y-2">
          {rows.map((wf) => (
            <li
              key={wf.id}
              className="flex items-center justify-between gap-2 rounded-md border p-3"
            >
              <button
                className="flex min-w-0 items-center gap-2 text-left hover:underline"
                onClick={() => router.push(`/workflows/${wf.id}`)}
              >
                <span className="truncate font-medium">{wf.name}</span>
                <Badge variant={STATUS_VARIANT[wf.status]}>{wf.status}</Badge>
                <span className="text-xs text-muted-foreground">{wf.run_count} runs</span>
              </button>
              <span className="flex shrink-0 gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    run(
                      setStatus.mutateAsync({
                        id: wf.id,
                        action: wf.status === "active" ? "pause" : "activate",
                      }),
                      wf.status === "active" ? "Paused" : "Activated",
                    )
                  }
                  disabled={setStatus.isPending}
                >
                  {wf.status === "active" ? "Pause" : "Activate"}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Duplicate ${wf.name}`}
                  onClick={() => run(duplicate.mutateAsync({ id: wf.id }), "Duplicated")}
                  disabled={duplicate.isPending}
                >
                  Duplicate
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Delete ${wf.name}`}
                  onClick={() => run(del.mutateAsync(wf.id), "Archived")}
                  disabled={del.isPending}
                >
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
