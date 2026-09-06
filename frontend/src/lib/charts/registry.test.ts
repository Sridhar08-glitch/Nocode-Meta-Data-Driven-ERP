import { describe, expect, it } from "vitest";

import { CHART_TYPES, getChartType, isMultiSeries } from "./registry";
import type { ChartType } from "./types";

describe("chart registry", () => {
  it("registers all 20 chart types with a data kind + render family", () => {
    expect(CHART_TYPES).toHaveLength(20);
    for (const def of CHART_TYPES) {
      expect(def.label).toBeTruthy();
      expect(["single", "multi", "xy", "matrix"]).toContain(def.dataKind);
      expect(def.render).toBeTruthy();
    }
    // every declared type resolves
    const types = CHART_TYPES.map((d) => d.type);
    expect(new Set(types).size).toBe(20); // no duplicates
  });

  it("resolves a type and flags multi-series", () => {
    expect(getChartType("bar")?.render).toBe("bar");
    expect(getChartType("donut")?.options?.donut).toBe(true);
    expect(getChartType("bogus" as ChartType)).toBeUndefined();
    expect(isMultiSeries("stacked_bar")).toBe(true);
    expect(isMultiSeries("bar")).toBe(false);
    expect(isMultiSeries("scatter")).toBe(false);
  });
});
