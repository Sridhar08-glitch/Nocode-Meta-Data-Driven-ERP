/** Shared aggregation (Phase F2.1) — used by pivot, chart, dashboard metrics. Pure. */
import { type Agg, type Row, toText } from "./types";

export function aggregate(values: number[], agg: Agg): number {
  if (agg === "count") return values.length;
  if (values.length === 0) return 0;
  if (agg === "sum") return values.reduce((a, b) => a + b, 0);
  if (agg === "avg") return values.reduce((a, b) => a + b, 0) / values.length;
  if (agg === "min") return Math.min(...values);
  return Math.max(...values);
}

/** Numeric value for a row+field; counts treat every row as 1 (valueField null). */
export function numericValue(row: Row, valueField: string | null | undefined): number {
  if (!valueField) return 1;
  const n = Number(row[valueField]);
  return Number.isFinite(n) ? n : 0;
}

/** Aggregate a flat list grouped by `groupField` → ordered {label,value} dataset. */
export function aggregateBy(
  rows: Row[],
  groupField: string,
  valueField: string | null | undefined,
  agg: Agg,
): { labels: string[]; values: number[] } {
  const buckets = new Map<string, number[]>();
  const order: string[] = [];
  for (const row of rows) {
    const key = toText(row[groupField]) || "—";
    if (!buckets.has(key)) {
      buckets.set(key, []);
      order.push(key);
    }
    buckets.get(key)!.push(numericValue(row, valueField));
  }
  return {
    labels: order,
    values: order.map((k) => aggregate(buckets.get(k)!, agg)),
  };
}
