"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import {
  type Dashboard,
  dashboardsApi,
  isPivotResult,
  type WidgetResult,
} from "@/lib/reporting/api";
import { useRunDashboard } from "@/lib/reporting/hooks";

/** Dashboard runtime (Phase F2.3): runs every widget and lays results out on the grid + PDF export. */
export function DashboardRuntime({ dashboard }: { dashboard: Dashboard }) {
  const run = useRunDashboard(dashboard.id);
  const { mutate } = run;
  useEffect(() => {
    mutate();
  }, [mutate]);

  const byId = new Map((run.data?.widgets ?? []).map((w) => [w.widget_id, w]));

  async function exportPdf() {
    try {
      await dashboardsApi.exportPdf(dashboard.id, dashboard.slug);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Export failed");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">{dashboard.name}</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? "Refreshing…" : "Refresh"}
          </Button>
          <Button variant="outline" size="sm" onClick={exportPdf}>
            Export PDF
          </Button>
        </div>
      </div>

      {run.isPending && !run.data && <Skeleton className="h-64 w-full" />}
      {run.isError && <ErrorState title="Couldn't run dashboard" />}
      {dashboard.widgets.length === 0 && <EmptyState title="No widgets" description="Add widgets in the builder." />}

      {dashboard.widgets.length > 0 && (
        <div className="grid grid-cols-12 gap-4">
          {dashboard.widgets.map((w) => (
            <section
              key={w.id}
              aria-label={w.title || w.widget_type}
              className="rounded-md border p-3"
              style={{ gridColumn: `span ${Math.min(Math.max(w.grid_w, 1), 12)}` }}
            >
              <h3 className="mb-2 text-sm font-medium text-muted-foreground">{w.title || w.widget_type}</h3>
              <WidgetBody widget={w} result={byId.get(w.id)} />
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function WidgetBody({ widget, result }: { widget: { widget_type: string }; result?: WidgetResult }) {
  if (!result) return <Skeleton className="h-16 w-full" />;
  if (result.error) return <p className="text-sm text-destructive">{result.error}</p>;

  if (result.result) {
    const r = result.result;
    if (isPivotResult(r)) {
      return <p className="text-sm text-muted-foreground">{r.row_values.length} × {r.column_values.length} pivot</p>;
    }
    if (widget.widget_type === "metric_card") {
      const first = r.rows[0];
      const metric = first ? Object.values(first).find((v) => typeof v === "number") ?? r.total_count : r.total_count;
      return <div className="text-3xl font-semibold tabular-nums">{String(metric)}</div>;
    }
    if (r.rows.length === 0) return <p className="text-sm text-muted-foreground">No rows.</p>;
    return (
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            {r.columns.map((c) => (
              <th key={c.key} className="text-left font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {r.rows.slice(0, 5).map((row, i) => (
            <tr key={i} className="border-b last:border-0">
              {r.columns.map((c) => (
                <td key={c.key}>{row[c.key] === null || row[c.key] === undefined ? "—" : String(row[c.key])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  // static widget (config echoed)
  const cfg = result.config ?? {};
  if (widget.widget_type === "text") return <p className="text-sm">{String(cfg.text ?? "")}</p>;
  if (widget.widget_type === "iframe" && typeof cfg.url === "string")
    return <iframe title={result.title} src={cfg.url} className="h-40 w-full rounded border" />;
  if (widget.widget_type === "quick_links" && Array.isArray(cfg.links))
    return (
      <ul className="space-y-1 text-sm">
        {(cfg.links as { label?: string; url?: string }[]).map((l, i) => (
          <li key={i}>
            <a className="text-primary hover:underline" href={l.url}>
              {l.label ?? l.url}
            </a>
          </li>
        ))}
      </ul>
    );
  return <p className="text-sm text-muted-foreground">No content.</p>;
}
