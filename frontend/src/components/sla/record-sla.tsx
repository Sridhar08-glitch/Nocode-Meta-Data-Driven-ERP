"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { SLAStatus } from "@/lib/sla/api";
import { usePauseSla, useRecordSla, useResumeSla } from "@/lib/sla/hooks";

const STATUS_VARIANT: Record<SLAStatus, "default" | "secondary" | "outline" | "destructive"> = {
  on_track: "default",
  met: "secondary",
  warning: "outline",
  paused: "secondary",
  breached: "destructive",
};

/** SLA status surfaced on a record (Phase F2.4): per-metric status + pause/resume. */
export function RecordSla({ entitySlug, recordId }: { entitySlug: string; recordId: string }) {
  const sla = useRecordSla(entitySlug, recordId);
  const pause = usePauseSla(entitySlug, recordId);
  const resume = useResumeSla(entitySlug, recordId);

  if (sla.isLoading) return <Skeleton className="h-16 w-full" />;
  if (sla.isError) return null; // SLA is optional context on a record
  const rows = sla.data?.results ?? [];
  if (rows.length === 0) return null;

  const anyActive = rows.some((r) => r.status === "on_track" || r.status === "warning");
  const anyPaused = rows.some((r) => r.status === "paused");

  async function act(kind: "pause" | "resume") {
    try {
      if (kind === "pause") await pause.mutateAsync();
      else await resume.mutateAsync();
      toast.success(kind === "pause" ? "SLA paused" : "SLA resumed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    }
  }

  return (
    <section aria-label="SLA status" className="space-y-2 rounded-md border p-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">SLA</h3>
        <span className="flex gap-1">
          {anyActive && (
            <Button variant="ghost" size="sm" onClick={() => act("pause")} disabled={pause.isPending}>
              Pause
            </Button>
          )}
          {anyPaused && (
            <Button variant="ghost" size="sm" onClick={() => act("resume")} disabled={resume.isPending}>
              Resume
            </Button>
          )}
        </span>
      </div>
      <ul className="space-y-1 text-sm">
        {rows.map((r) => (
          <li key={r.id} className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2">
              <Badge variant={STATUS_VARIANT[r.status]}>{r.status.replace("_", " ")}</Badge>
              <span>{r.metric_key}</span>
            </span>
            <span className="text-xs text-muted-foreground">
              due {r.target_at ? new Date(r.target_at).toLocaleString() : "—"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
