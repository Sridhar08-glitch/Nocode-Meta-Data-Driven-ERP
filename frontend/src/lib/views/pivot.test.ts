import { describe, expect, it } from "vitest";

import { cellKey, drillThrough, pivot } from "./pivot";

const rows = [
  { id: "1", region: "EU", stage: "open", value: 100 },
  { id: "2", region: "EU", stage: "won", value: 200 },
  { id: "3", region: "US", stage: "open", value: 50 },
  { id: "4", region: "EU", stage: "open", value: 10 },
];

describe("pivot", () => {
  it("aggregates sum across row×col with totals", () => {
    const p = pivot(rows, "region", "stage", "value", "sum");
    expect(p.rowKeys).toEqual(["EU", "US"]);
    expect(p.colKeys).toEqual(["open", "won"]);
    expect(p.cells[cellKey("EU", "open")]).toBe(110);
    expect(p.cells[cellKey("EU", "won")]).toBe(200);
    expect(p.cells[cellKey("US", "open")]).toBe(50);
    expect(p.rowTotals["EU"]).toBe(310);
    expect(p.colTotals["open"]).toBe(160);
    expect(p.grandTotal).toBe(360);
  });

  it("counts rows when there is no value field", () => {
    const p = pivot(rows, "region", "stage", null, "count");
    expect(p.cells[cellKey("EU", "open")]).toBe(2);
    expect(p.grandTotal).toBe(4);
  });

  it("buckets blank keys under —", () => {
    const p = pivot([{ id: "1", value: 5 }], "region", "stage", "value", "sum");
    expect(p.rowKeys).toEqual(["—"]);
    expect(p.colKeys).toEqual(["—"]);
    expect(p.cells[cellKey("—", "—")]).toBe(5);
  });
});

describe("drillThrough", () => {
  it("returns the rows behind a specific cell", () => {
    expect(drillThrough(rows, "region", "stage", "EU", "open").map((r) => r.id)).toEqual(["1", "4"]);
  });
  it("returns a whole row or column when a key is null", () => {
    expect(drillThrough(rows, "region", "stage", "EU", null).map((r) => r.id)).toEqual(["1", "2", "4"]);
    expect(drillThrough(rows, "region", "stage", null, "open").map((r) => r.id)).toEqual(["1", "3", "4"]);
  });
});
