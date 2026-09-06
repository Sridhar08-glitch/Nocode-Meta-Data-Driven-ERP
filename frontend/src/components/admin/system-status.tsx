"use client";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { useReadiness } from "@/lib/ops/hooks";

/**
 * System status (Phase P1.6) — live infra readiness (DB / cache / broker) from the
 * unauthenticated `/readyz/` probe, polled every 15s. Complements the tenant business-metrics
 * panel: this is process/dependency health, not per-workspace data.
 */
export function SystemStatus() {
  const readiness = useReadiness();

  if (readiness.isLoading) return <Skeleton className="h-24 w-full" />;
  if (readiness.isError) return <ErrorState title="Couldn't reach the readiness probe" />;
  const data = readiness.data;
  if (!data) return null;

  const components = Object.entries(data.checks);

  return (
    <section className="space-y-2" aria-label="System status">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-medium text-muted-foreground">System status</h2>
        <Badge variant={data.status === "ready" ? "default" : "destructive"}>
          {data.status === "ready" ? "All systems operational" : "Degraded"}
        </Badge>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {components.map(([name, c]) => (
          <div key={name} aria-label={`status-${name}`} className="rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <span className="font-medium capitalize">{name}</span>
              <span
                aria-label={c.ok ? `${name} up` : `${name} down`}
                className={`inline-block size-2.5 rounded-full ${c.ok ? "bg-emerald-500" : "bg-destructive"}`}
              />
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {c.ok ? `${c.latency_ms} ms` : c.detail}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
