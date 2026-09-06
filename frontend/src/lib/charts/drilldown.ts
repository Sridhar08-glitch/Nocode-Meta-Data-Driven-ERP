/**
 * Shared drill-down (Phase F2.2). One implementation for every chart type: given a clicked
 * selector, resolve the underlying source records by reusing the F2.1 grouping primitives
 * (`groupByField` / `drillThrough`). The records runtime then opens/filters them by id.
 */
import { groupByField } from "@/lib/views/grouping";
import { drillThrough } from "@/lib/views/pivot";
import { type Row, rowId } from "@/lib/views/types";

import { getChartType } from "./registry";
import type { ChartSelector, ChartSpec } from "./types";

/** Resolve the source rows behind a clicked chart element. */
export function resolveDrilldown(spec: ChartSpec, rows: Row[], selector: ChartSelector): Row[] {
  const def = getChartType(spec.type);
  if (!def) return [];

  if (selector.kind === "record") {
    return rows.filter((r) => rowId(r) === selector.recordId);
  }

  if (selector.kind === "cell") {
    if (!spec.series) return [];
    return drillThrough(rows, spec.x.field, spec.series.field, selector.row, selector.col);
  }

  // label selector → all rows in that category (single-series / one axis of a matrix)
  const group = groupByField(rows, spec.x.field).find((g) => g.label === selector.label);
  return group ? group.records : [];
}

/** The record ids behind a clicked element (handed to the records runtime). */
export function drilldownRecordIds(spec: ChartSpec, rows: Row[], selector: ChartSelector): string[] {
  return resolveDrilldown(spec, rows, selector).map(rowId);
}
