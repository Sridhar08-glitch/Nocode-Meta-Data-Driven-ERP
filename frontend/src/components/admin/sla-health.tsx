"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { useSlaDashboard } from "@/lib/sla/hooks";

const STATUSES = ["breached", "warning", "on_track", "met", "paused"] as const;

/** SLA health counts (Phase F3.2) — reuses the existing `/api/v1/sla/dashboard/` hook. */
export function SlaHealth() {
  const dashboard = useSlaDashboard();
  if (dashboard.isLoading) return <Skeleton className="h-20 w-full" />;
  const d = dashboard.data;
  if (!d) return null;

  return (
    <section className="space-y-2" aria-label="SLA health">
      <h2 className="text-sm font-medium text-muted-foreground">SLA status</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {STATUSES.map((k) => (
          <div key={k} aria-label={`sla-${k}`} className="rounded-lg border p-4 text-center">
            <div className="text-2xl font-semibold tabular-nums">{d[k]}</div>
            <div className="text-xs text-muted-foreground">{k.replace("_", " ")}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
