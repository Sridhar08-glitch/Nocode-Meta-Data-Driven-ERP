import { describe, expect, it } from "vitest";

import { dependencyEdges, ganttItems } from "./gantt";

const cfg = {
  startField: "start",
  endField: "end",
  progressField: "pct",
  dependencyField: "deps",
};

describe("ganttItems", () => {
  it("positions bars across the overall span with progress + deps", () => {
    const rows = [
      { id: "a", start: "2026-01-01", end: "2026-01-11", pct: 50, deps: [] },
      { id: "b", start: "2026-01-11", end: "2026-01-21", pct: 150, deps: ["a"] },
    ];
    const items = ganttItems(rows, cfg);
    expect(items).toHaveLength(2);
    expect(items[0].left).toBe(0); // earliest start → left edge
    expect(items[1].left).toBeCloseTo(50, 0);
    expect(items[0].progress).toBe(0.5);
    expect(items[1].progress).toBe(1); // clamped from 150
    expect(items[1].dependsOn).toEqual(["a"]);
  });

  it("drops rows with invalid or inverted dates", () => {
    const rows = [
      { id: "ok", start: "2026-01-01", end: "2026-01-02" },
      { id: "bad", start: "x", end: "2026-01-02" },
      { id: "inv", start: "2026-02-01", end: "2026-01-01" },
    ];
    expect(ganttItems(rows, { startField: "start", endField: "end" }).map((i) => i.id)).toEqual(["ok"]);
  });

  it("normalises a single dependency string to an array and returns [] for no data", () => {
    const items = ganttItems([{ id: "a", start: "2026-01-01", end: "2026-01-02", deps: "z" }], cfg);
    expect(items[0].dependsOn).toEqual(["z"]);
    expect(ganttItems([], cfg)).toEqual([]);
  });
});

describe("dependencyEdges", () => {
  it("builds edges and drops dangling references", () => {
    const items = ganttItems(
      [
        { id: "a", start: "2026-01-01", end: "2026-01-02", deps: [] },
        { id: "b", start: "2026-01-02", end: "2026-01-03", deps: ["a", "ghost"] },
      ],
      cfg,
    );
    expect(dependencyEdges(items)).toEqual([{ from: "a", to: "b" }]);
  });
});
