import { describe, expect, it } from "vitest";

import type { EntityMeta, FieldMeta } from "@/lib/metadata/types";
import type { Row } from "@/lib/views/types";

import { buildChartData } from "./spec";
import { validateChartSpec } from "./spec";
import type { ChartSpec } from "./types";

function field(slug: string, t: string): FieldMeta {
  return { slug, name: slug, field_type: t } as unknown as FieldMeta;
}
const entity = {
  id: "e1",
  slug: "deals",
  fields: [field("stage", "select"), field("region", "select"), field("amount", "currency"), field("x", "decimal"), field("y", "decimal"), field("size", "decimal")],
} as unknown as EntityMeta;

const rows: Row[] = [
  { id: "1", stage: "open", region: "EU", amount: 100, x: 1, y: 2, size: 5 },
  { id: "2", stage: "open", region: "US", amount: 50, x: 3, y: 4, size: 6 },
  { id: "3", stage: "won", region: "EU", amount: 200, x: 5, y: 6, size: 7 },
];

const spec = (over: Partial<ChartSpec>): ChartSpec => ({
  type: "bar",
  x: { field: "stage" },
  agg: "sum",
  valueField: "amount",
  ...over,
});

describe("validateChartSpec", () => {
  it("validates a single-series spec", () => {
    expect(validateChartSpec(spec({ type: "bar" }), entity).valid).toBe(true);
  });
  it("rejects an unsupported type", () => {
    expect(validateChartSpec(spec({ type: "nope" as ChartSpec["type"] }), entity).errors[0]).toMatch(/Unsupported/);
  });
  it("requires a value field for non-count aggregations", () => {
    expect(validateChartSpec(spec({ agg: "sum", valueField: null }), entity).errors).toContain("Value field is required.");
  });
  it("allows count without a value field", () => {
    expect(validateChartSpec(spec({ agg: "count", valueField: null }), entity).valid).toBe(true);
  });
  it("requires a series field for multi-series charts", () => {
    expect(validateChartSpec(spec({ type: "stacked_bar" }), entity).errors).toContain("Series field is required.");
    expect(validateChartSpec(spec({ type: "stacked_bar", series: { field: "region" } }), entity).valid).toBe(true);
  });
  it("requires x + y for xy charts and size for bubbles", () => {
    expect(validateChartSpec(spec({ type: "scatter", x: { field: "x" } }), entity).errors).toContain("Y field is required.");
    expect(validateChartSpec(spec({ type: "scatter", x: { field: "x" }, y: { field: "y" } }), entity).valid).toBe(true);
    expect(validateChartSpec(spec({ type: "bubble", x: { field: "x" }, y: { field: "y" } }), entity).errors).toContain("Size field is required.");
  });
  it("flags a field that isn't on the entity", () => {
    expect(validateChartSpec(spec({ x: { field: "ghost" } }), entity).errors[0]).toMatch(/not a field/);
  });
});

describe("buildChartData", () => {
  it("builds a single series with values + retained record ids", () => {
    const data = buildChartData(spec({ type: "bar" }), rows);
    expect(data.kind).toBe("categorical");
    if (data.kind !== "categorical") throw new Error();
    expect(data.labels).toEqual(["open", "won"]);
    expect(data.series).toHaveLength(1);
    expect(data.series[0].points[0]).toMatchObject({ label: "open", value: 150, recordIds: ["1", "2"] });
    expect(data.series[0].points[1]).toMatchObject({ label: "won", value: 200, recordIds: ["3"] });
  });

  it("builds multi-series from a pivot, each datum keeping its records", () => {
    const data = buildChartData(spec({ type: "grouped_bar", series: { field: "region" } }), rows);
    if (data.kind !== "categorical") throw new Error();
    expect(data.labels).toEqual(["open", "won"]);
    expect(data.series.map((s) => s.name)).toEqual(["EU", "US"]);
    const euOpen = data.series[0].points.find((p) => p.label === "open")!;
    expect(euOpen).toMatchObject({ value: 100, recordIds: ["1"] });
  });

  it("builds xy points, dropping non-numeric, keeping size for bubbles", () => {
    const data = buildChartData(spec({ type: "bubble", x: { field: "x" }, y: { field: "y" }, sizeField: "size" }), [
      ...rows,
      { id: "bad", x: "nope", y: 1 },
    ]);
    if (data.kind !== "xy") throw new Error();
    expect(data.points).toHaveLength(3);
    expect(data.points[0]).toMatchObject({ x: 1, y: 2, size: 5, recordId: "1" });
  });

  it("builds a matrix for heatmaps", () => {
    const data = buildChartData(spec({ type: "heatmap", series: { field: "region" } }), rows);
    if (data.kind !== "matrix") throw new Error();
    expect(data.rowKeys).toEqual(["open", "won"]);
    expect(data.colKeys).toEqual(["EU", "US"]);
    const cell = data.cells.find((c) => c.row === "open" && c.col === "EU")!;
    expect(cell).toMatchObject({ value: 100, recordIds: ["1"] });
  });

  it("counts rows when there is no value field", () => {
    const data = buildChartData(spec({ type: "bar", agg: "count", valueField: null }), rows);
    if (data.kind !== "categorical") throw new Error();
    expect(data.series[0].points.map((p) => p.value)).toEqual([2, 1]);
  });
});
