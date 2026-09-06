import { describe, expect, it } from "vitest";

import { aggregate, aggregateBy, numericValue } from "./aggregation";

describe("aggregate", () => {
  it("computes each aggregation", () => {
    expect(aggregate([1, 2, 3, 4], "count")).toBe(4);
    expect(aggregate([1, 2, 3, 4], "sum")).toBe(10);
    expect(aggregate([1, 2, 3, 4], "avg")).toBe(2.5);
    expect(aggregate([3, 1, 4], "min")).toBe(1);
    expect(aggregate([3, 1, 4], "max")).toBe(4);
  });
  it("handles empty input (count 0, others 0)", () => {
    expect(aggregate([], "count")).toBe(0);
    expect(aggregate([], "sum")).toBe(0);
    expect(aggregate([], "avg")).toBe(0);
    expect(aggregate([], "max")).toBe(0);
  });
});

describe("numericValue", () => {
  it("returns 1 for count (no value field) and coerces otherwise", () => {
    expect(numericValue({ amount: "5" }, null)).toBe(1);
    expect(numericValue({ amount: "5" }, "amount")).toBe(5);
    expect(numericValue({ amount: "x" }, "amount")).toBe(0); // non-numeric → 0
  });
});

describe("aggregateBy", () => {
  it("groups + aggregates in first-seen order", () => {
    const rows = [
      { stage: "open", v: 10 },
      { stage: "won", v: 5 },
      { stage: "open", v: 20 },
    ];
    expect(aggregateBy(rows, "stage", "v", "sum")).toEqual({ labels: ["open", "won"], values: [30, 5] });
    expect(aggregateBy(rows, "stage", null, "count")).toEqual({ labels: ["open", "won"], values: [2, 1] });
  });
  it("buckets blank group values under —", () => {
    expect(aggregateBy([{ v: 1 }], "stage", null, "count")).toEqual({ labels: ["—"], values: [1] });
  });
});
