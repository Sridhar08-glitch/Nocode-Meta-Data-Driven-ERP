/** Pivot (Phase F2.1) — in-memory row×column aggregation + drill-down. Pure (never raw GROUP BY). */
import { aggregate, numericValue } from "./aggregation";
import { type Agg, type PivotResult, type Row, toText } from "./types";

/** Composite cell key. Uses a control-char separator that won't appear in stringified values. */
export function cellKey(rowKey: string, colKey: string): string {
  return `${rowKey}${colKey}`;
}

export function pivot(
  rows: Row[],
  rowField: string,
  colField: string,
  valueField: string | null | undefined,
  agg: Agg,
): PivotResult {
  const buckets = new Map<string, number[]>();
  const rowKeys: string[] = [];
  const colKeys: string[] = [];
  const seenRow = new Set<string>();
  const seenCol = new Set<string>();

  for (const row of rows) {
    const rk = toText(row[rowField]) || "—";
    const ck = toText(row[colField]) || "—";
    if (!seenRow.has(rk)) {
      seenRow.add(rk);
      rowKeys.push(rk);
    }
    if (!seenCol.has(ck)) {
      seenCol.add(ck);
      colKeys.push(ck);
    }
    const key = cellKey(rk, ck);
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key)!.push(numericValue(row, valueField));
  }

  const cells: Record<string, number> = {};
  const rowTotals: Record<string, number> = {};
  const colTotals: Record<string, number> = {};
  for (const rk of rowKeys) {
    const rowVals: number[] = [];
    for (const ck of colKeys) {
      const key = cellKey(rk, ck);
      const vals = buckets.get(key) ?? [];
      cells[key] = aggregate(vals, agg);
      rowVals.push(...vals);
    }
    rowTotals[rk] = aggregate(rowVals, agg);
  }
  const allVals: number[] = [];
  for (const ck of colKeys) {
    const colVals: number[] = [];
    for (const rk of rowKeys) colVals.push(...(buckets.get(cellKey(rk, ck)) ?? []));
    colTotals[ck] = aggregate(colVals, agg);
    allVals.push(...colVals);
  }
  return { rowKeys, colKeys, cells, rowTotals, colTotals, grandTotal: aggregate(allVals, agg) };
}

/** Drill-down: the underlying rows behind a pivot cell (or a whole row/column when a key is null). */
export function drillThrough(
  rows: Row[],
  rowField: string,
  colField: string,
  rowKey: string | null,
  colKey: string | null,
): Row[] {
  return rows.filter((row) => {
    const rk = toText(row[rowField]) || "—";
    const ck = toText(row[colField]) || "—";
    return (rowKey === null || rk === rowKey) && (colKey === null || ck === colKey);
  });
}
