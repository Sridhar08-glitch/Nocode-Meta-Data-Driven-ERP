"use client";

import { DashboardRuntime } from "@/components/reporting/dashboard-runtime";
import { Skeleton } from "@/components/ui/skeleton";
import type { Dashboard } from "@/lib/reporting/api";
import { useDashboards } from "@/lib/reporting/hooks";
import { useActiveApp } from "@/lib/studio/active-app";
import type { HomeLayout, HomeWidget } from "@/lib/studio/api";
import { useResolvedHome } from "@/lib/studio/hooks";

/**
 * Home runtime (Phase F2.8 + F3-role-dashboards). Renders the resolved HomeLayout for the active
 * app; server-side resolution precedence is personal > role > app > workspace, so each role is
 * auto-routed to its own home after login (DG-5). A widget of `type: "dashboard"` with
 * `config.dashboard_slug` renders the referenced Dashboard through the F2.3 dashboard runtime
 * (real KPIs / reports / charts) — reused, not re-implemented. Other widget types render as
 * lightweight titled cards. When no published layout applies, `fallback` is shown.
 */
export function HomeRuntime({ fallback }: { fallback: React.ReactNode }) {
  const { activeAppId } = useActiveApp();
  const resolved = useResolvedHome(activeAppId ?? undefined);
  const dashboards = useDashboards();

  if (resolved.isLoading) return <Skeleton className="h-40 w-full" />;

  const layout = resolved.data as HomeLayout | Record<string, never> | undefined;
  const widgets = layout && "widgets" in layout ? layout.widgets : [];

  if (!widgets || widgets.length === 0) return <>{fallback}</>;

  const bySlug = new Map<string, Dashboard>(
    (dashboards.data?.results ?? []).map((d) => [d.slug, d]),
  );

  return (
    <div className="space-y-4">
      {layout && "name" in layout && <h1 className="text-2xl font-semibold">{layout.name}</h1>}
      <div className="grid grid-cols-12 gap-4">
        {widgets.map((w, i) => (
          <HomeWidgetView key={i} widget={w} index={i} bySlug={bySlug} />
        ))}
      </div>
    </div>
  );
}

function HomeWidgetView({
  widget,
  index,
  bySlug,
}: {
  widget: HomeWidget;
  index: number;
  bySlug: Map<string, Dashboard>;
}) {
  // A dashboard reference → render the full F2.3 dashboard runtime, spanning the row.
  if (widget.type === "dashboard") {
    const slug = typeof widget.config?.dashboard_slug === "string" ? widget.config.dashboard_slug : "";
    const dashboard = bySlug.get(slug);
    return (
      <div className="col-span-12" aria-label={`Widget ${index + 1}`}>
        {dashboard ? (
          <DashboardRuntime dashboard={dashboard} />
        ) : (
          <div className="rounded-lg border p-4">
            <div className="text-sm font-medium">{widget.title || "Dashboard"}</div>
            <div className="mt-1 text-xs text-muted-foreground">Dashboard not found.</div>
          </div>
        )}
      </div>
    );
  }
  const span = Math.min(Math.max(widget.width ?? 4, 1), 12);
  return (
    <div
      className="rounded-lg border p-4"
      style={{ gridColumn: `span ${span} / span ${span}` }}
      aria-label={`Widget ${index + 1}`}
    >
      <div className="text-sm font-medium">{widget.title || widget.type}</div>
      <div className="mt-1 text-xs uppercase tracking-wide text-muted-foreground">{widget.type}</div>
    </div>
  );
}
