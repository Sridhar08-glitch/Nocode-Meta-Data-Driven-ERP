"use client";

import { aggregateBy } from "@/lib/views/aggregation";
import { type Agg, type ChartType, type Row } from "@/lib/views/types";

export interface ChartViewProps {
  rows: Row[];
  chartType: ChartType;
  groupField: string;
  valueField?: string | null;
  agg: Agg;
}

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(2));

/**
 * Lightweight, dependency-free chart over a shared aggregated dataset (Phase F2.1). Bar/line/area
 * render as proportional bars; pie renders proportion labels. The full Recharts engine (20 types)
 * is F2.2 — this consumes the same `aggregateBy` dataset it will. A data list provides the a11y
 * fallback.
 */
export function ChartView({ rows, chartType, groupField, valueField, agg }: ChartViewProps) {
  const { labels, values } = aggregateBy(rows, groupField, valueField ?? null, agg);
  if (labels.length === 0) return <p className="text-sm text-muted-foreground">No data.</p>;
  const max = Math.max(...values, 1);
  const total = values.reduce((a, b) => a + b, 0) || 1;

  return (
    <div role="img" aria-label={`${chartType} chart of ${agg} by ${groupField}`} className="space-y-1">
      {labels.map((labelText, i) => (
        <div key={labelText} className="flex items-center gap-2 text-sm">
          <span className="w-32 shrink-0 truncate text-muted-foreground">{labelText}</span>
          <div className="relative h-5 flex-1 rounded bg-muted/40">
            <div
              data-testid="chart-bar"
              data-value={values[i]}
              className="h-5 rounded bg-primary"
              style={{ width: `${chartType === "pie" ? (values[i] / total) * 100 : (values[i] / max) * 100}%` }}
            />
          </div>
          <span className="w-16 shrink-0 text-right tabular-nums">
            {chartType === "pie" ? `${Math.round((values[i] / total) * 100)}%` : fmt(values[i])}
          </span>
        </div>
      ))}
    </div>
  );
}
