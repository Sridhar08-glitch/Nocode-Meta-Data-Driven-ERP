/**
 * ChartSpec builder + validator (Phase F2.2). Produces normalized {@link ChartData} by composing
 * the F2.1 aggregation primitives — `groupByField`+`aggregate` (single series) and `pivot`+
 * `drillThrough` (multi-series / matrix). No chart-specific aggregation. Every datum keeps record ids.
 */
import type { EntityMeta } from "@/lib/metadata/types";
import { aggregate, numericValue } from "@/lib/views/aggregation";
import { hasField } from "@/lib/views/engine";
import { groupByField } from "@/lib/views/grouping";
import { cellKey, drillThrough, pivot } from "@/lib/views/pivot";
import { type Agg, type Row, rowId, toText } from "@/lib/views/types";

import { getChartType } from "./registry";
import type { ChartData, ChartSpec, ChartValidation } from "./types";

const AGGS: Agg[] = ["count", "sum", "avg", "min", "max"];

export function validateChartSpec(spec: ChartSpec, entity: EntityMeta): ChartValidation {
  const errors: string[] = [];
  const def = getChartType(spec.type);
  if (!def) return { valid: false, errors: [`Unsupported chart type "${spec.type}".`] };

  const need = (slug: string | undefined | null, label: string) => {
    if (!slug) errors.push(`${label} is required.`);
    else if (!hasField(entity, slug)) errors.push(`${label} "${slug}" is not a field on this entity.`);
  };

  if (def.dataKind === "xy") {
    need(spec.x.field, "X field");
    need(spec.y?.field, "Y field");
    if (def.options?.bubble) need(spec.sizeField ?? undefined, "Size field");
  } else {
    need(spec.x.field, def.dataKind === "matrix" ? "Row field" : "Category field");
    if (def.dataKind === "multi" || def.dataKind === "matrix") need(spec.series?.field, "Series field");
    if (!AGGS.includes(spec.agg)) errors.push("A valid aggregation is required.");
    if (spec.agg !== "count") need(spec.valueField ?? undefined, "Value field");
  }
  return { valid: errors.length === 0, errors };
}

function seriesName(spec: ChartSpec): string {
  if (spec.agg === "count") return "count";
  return `${spec.agg}(${spec.valueField})`;
}

export function buildChartData(spec: ChartSpec, rows: Row[]): ChartData {
  const def = getChartType(spec.type);
  const kind = def?.dataKind ?? "single";

  if (kind === "xy") {
    const points = rows
      .map((row) => ({
        x: Number(row[spec.x.field]),
        y: Number(row[spec.y?.field ?? ""]),
        size: spec.sizeField ? Number(row[spec.sizeField]) : undefined,
        recordId: rowId(row),
        label: toText(row[spec.x.field]),
      }))
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
    return { kind: "xy", points };
  }

  if (kind === "multi") {
    const p = pivot(rows, spec.x.field, spec.series!.field, spec.valueField ?? null, spec.agg);
    const series = p.colKeys.map((ck) => ({
      name: ck,
      points: p.rowKeys.map((rk) => ({
        label: rk,
        value: p.cells[cellKey(rk, ck)] ?? 0,
        recordIds: drillThrough(rows, spec.x.field, spec.series!.field, rk, ck).map(rowId),
      })),
    }));
    return { kind: "categorical", labels: p.rowKeys, series };
  }

  if (kind === "matrix") {
    const p = pivot(rows, spec.x.field, spec.series!.field, spec.valueField ?? null, spec.agg);
    const cells = p.rowKeys.flatMap((rk) =>
      p.colKeys.map((ck) => ({
        row: rk,
        col: ck,
        value: p.cells[cellKey(rk, ck)] ?? 0,
        recordIds: drillThrough(rows, spec.x.field, spec.series!.field, rk, ck).map(rowId),
      })),
    );
    return { kind: "matrix", rowKeys: p.rowKeys, colKeys: p.colKeys, cells };
  }

  // single series
  const groups = groupByField(rows, spec.x.field);
  const points = groups.map((g) => ({
    label: g.label,
    value: aggregate(g.records.map((r) => numericValue(r, spec.valueField ?? null)), spec.agg),
    recordIds: g.records.map(rowId),
  }));
  return { kind: "categorical", labels: groups.map((g) => g.label), series: [{ name: seriesName(spec), points }] };
}
