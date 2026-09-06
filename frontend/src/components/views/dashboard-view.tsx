"use client";

import { aggregate, numericValue } from "@/lib/views/aggregation";
import {
  type ChartConfig,
  type DashboardWidgetDef,
  type MetricConfig,
  type PivotConfig,
  type Row,
} from "@/lib/views/types";

import { ChartView } from "./chart-view";
import { PivotView } from "./pivot-view";

export interface DashboardViewProps {
  rows: Row[];
  widgets: DashboardWidgetDef[];
}

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2));

/** Dashboard widget composition over the shared aggregations (Phase F2.1). */
export function DashboardView({ rows, widgets }: DashboardViewProps) {
  if (widgets.length === 0) return <p className="text-sm text-muted-foreground">No widgets.</p>;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {widgets.map((w) => (
        <section key={w.id} aria-label={w.title} className="rounded-md border p-3">
          <h3 className="mb-2 text-sm font-medium text-muted-foreground">{w.title}</h3>
          <Widget rows={rows} widget={w} />
        </section>
      ))}
    </div>
  );
}

function Widget({ rows, widget }: { rows: Row[]; widget: DashboardWidgetDef }) {
  if (widget.kind === "metric") {
    const cfg = widget.config as MetricConfig;
    const value = aggregate(rows.map((r) => numericValue(r, cfg.valueField)), cfg.agg);
    return <div className="text-3xl font-semibold tabular-nums">{fmt(value)}</div>;
  }
  if (widget.kind === "chart") {
    const cfg = widget.config as ChartConfig;
    return (
      <ChartView
        rows={rows}
        chartType={cfg.chartType}
        groupField={cfg.groupField}
        valueField={cfg.valueField}
        agg={cfg.agg}
      />
    );
  }
  const cfg = widget.config as PivotConfig;
  return (
    <PivotView rows={rows} rowField={cfg.rowField} colField={cfg.colField} valueField={cfg.valueField} agg={cfg.agg} />
  );
}
