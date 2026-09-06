"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { useSlaDashboard } from "@/lib/helpdesk/hooks";

/** Native SLA-dashboard panel (Phase P2.11) — workspace SLA health (breached / warning / on-track / met /
 * paused). Reuses the SLA engine; all counts are computed server-side. */
export function SlaPanel() {
  const dash = useSlaDashboard();

  if (dash.isLoading) return <Skeleton className="h-40 w-full" />;
  if (dash.isError) return <ErrorState title="Couldn't load SLA dashboard" />;
  if (!dash.data) return null;

  const d = dash.data;
  const cards: { key: string; label: string; value: number; tone: string }[] = [
    { key: "breached", label: "Breached", value: d.breached, tone: "border-destructive/40 bg-destructive/5 text-destructive" },
    { key: "warning", label: "Warning", value: d.warning, tone: "border-amber-500/40 bg-amber-500/5 text-amber-600" },
    { key: "on_track", label: "On track", value: d.on_track, tone: "border-emerald-500/40 bg-emerald-500/5 text-emerald-600" },
    { key: "met", label: "Met", value: d.met, tone: "border-emerald-500/40 bg-emerald-500/5 text-emerald-600" },
    { key: "paused", label: "Paused", value: d.paused, tone: "border-muted-foreground/30 bg-muted/40 text-muted-foreground" },
  ];

  return (
    <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map((c) => (
        <div key={c.key} className={`space-y-1 rounded-lg border p-4 ${c.tone}`}>
          <p className="text-xs font-medium uppercase tracking-wide">{c.label}</p>
          <p className="font-mono text-2xl font-semibold">{c.value}</p>
        </div>
      ))}
    </section>
  );
}
