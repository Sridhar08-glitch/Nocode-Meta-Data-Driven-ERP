import { describe, expect, it } from "vitest";

import type { Row } from "@/lib/views/types";

import { drilldownRecordIds, resolveDrilldown } from "./drilldown";
import type { ChartSpec } from "./types";

const rows: Row[] = [
  { id: "1", stage: "open", region: "EU" },
  { id: "2", stage: "open", region: "US" },
  { id: "3", stage: "won", region: "EU" },
];
const spec: ChartSpec = { type: "bar", x: { field: "stage" }, agg: "count", series: { field: "region" } };

describe("resolveDrilldown", () => {
  it("resolves a category (label) to its rows", () => {
    expect(resolveDrilldown(spec, rows, { kind: "label", label: "open" }).map((r) => r.id)).toEqual(["1", "2"]);
  });
  it("resolves a multi-series cell via the two grouping fields", () => {
    expect(resolveDrilldown(spec, rows, { kind: "cell", row: "open", col: "EU" }).map((r) => r.id)).toEqual(["1"]);
  });
  it("resolves a single record (scatter point)", () => {
    expect(resolveDrilldown(spec, rows, { kind: "record", recordId: "3" }).map((r) => r.id)).toEqual(["3"]);
  });
  it("returns [] for a cell selector when no series is configured", () => {
    const noSeries: ChartSpec = { type: "bar", x: { field: "stage" }, agg: "count" };
    expect(resolveDrilldown(noSeries, rows, { kind: "cell", row: "open", col: "EU" })).toEqual([]);
  });
  it("returns [] for an unknown chart type", () => {
    expect(resolveDrilldown({ ...spec, type: "nope" as ChartSpec["type"] }, rows, { kind: "label", label: "open" })).toEqual([]);
  });
  it("returns [] for an unmatched label", () => {
    expect(resolveDrilldown(spec, rows, { kind: "label", label: "ghost" })).toEqual([]);
  });

  it("drilldownRecordIds returns the ids", () => {
    expect(drilldownRecordIds(spec, rows, { kind: "label", label: "won" })).toEqual(["3"]);
  });
});
