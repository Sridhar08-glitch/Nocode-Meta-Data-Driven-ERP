"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import type { TenantHealth } from "@/lib/admin/api";
import { useTenantHealth } from "@/lib/admin/hooks";

function Kpi({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-lg border p-4" aria-label={label}>
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
      {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

const dash = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v);

/** Tenant Health dashboard (Phase F3.1/F3.2): workspace KPIs from `/api/v1/admin/health/`. */
export function TenantHealthPanel() {
  const health = useTenantHealth();

  if (health.isLoading) return <Skeleton className="h-48 w-full" />;
  if (health.isError) return <ErrorState title="Couldn't load tenant health" />;
  const h = health.data as TenantHealth | undefined;
  // A non-admin hitting this page gets a 403 whose body has no health shape — guard
  // against it so the panel shows a clean message instead of crashing on h.workflows.
  if (!h || !h.workflows) {
    return <ErrorState title="Tenant health unavailable" description="You don't have permission to view workspace health." />;
  }

  return (
    <div className="space-y-5">
      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">Workflows</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <Kpi label="Success rate" value={`${Math.round(h.workflows.success_rate * 100)}%`} />
          <Kpi label="Total runs" value={h.workflows.total} />
          <Kpi label="Failed" value={h.workflows.failed} />
          <Kpi label="Running" value={h.workflows.running} />
          <Kpi label="Queued" value={h.workflows.queued} />
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">Workflow latency (ms)</h2>
        <div className="grid grid-cols-3 gap-3">
          <Kpi label="p50" value={dash(h.workflow_latency_ms.p50)} />
          <Kpi label="p95" value={dash(h.workflow_latency_ms.p95)} />
          <Kpi label="p99" value={dash(h.workflow_latency_ms.p99)} />
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">Active users</h2>
        <div className="grid grid-cols-3 gap-3">
          <Kpi label="DAU" value={h.activity.dau} />
          <Kpi label="WAU" value={h.activity.wau} />
          <Kpi label="MAU" value={h.activity.mau} />
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">Records & storage</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Kpi label="Records 24h" value={h.records.created_24h} />
          <Kpi label="Records 7d" value={h.records.created_7d} />
          <Kpi label="Entities" value={h.storage.entity_count} />
          <Kpi label="Rows (est.)" value={h.storage.row_count_estimate} />
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-muted-foreground">Errors (24h)</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Kpi label="Error rate" value={`${Math.round(h.errors.error_rate_24h * 100)}%`} />
          <Kpi label="Runs" value={h.errors.workflow_runs_24h} />
          <Kpi label="Failures" value={h.errors.workflow_failures_24h} />
        </div>
      </section>

      <p className="text-xs text-muted-foreground">
        API latency, queue depth, and plan-limit metrics are not yet instrumented (shown as “—”). AI
        metrics are intentionally absent (no-AI platform).
      </p>
    </div>
  );
}
