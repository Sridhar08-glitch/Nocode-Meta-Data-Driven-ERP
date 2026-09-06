import { describe, expect, it } from "vitest";

import { groupByField, UNASSIGNED } from "./grouping";

const rows = [
  { id: "1", stage: "open" },
  { id: "2", stage: "won" },
  { id: "3", stage: "open" },
  { id: "4", stage: null },
];

describe("groupByField", () => {
  it("groups by value in first-seen order", () => {
    const g = groupByField(rows, "stage");
    expect(g.map((x) => x.key)).toEqual(["open", "won", UNASSIGNED]);
    expect(g[0].records).toHaveLength(2);
    expect(g[2].label).toBe("Unassigned");
  });

  it("honours an explicit column order and keeps empty columns", () => {
    const g = groupByField(rows, "stage", ["won", "open", "lost"]);
    expect(g.map((x) => x.key)).toEqual(["won", "open", "lost", UNASSIGNED]);
    expect(g.find((x) => x.key === "lost")!.records).toEqual([]);
  });

  it("always sorts the unassigned column last", () => {
    const g = groupByField([{ id: "1", stage: null }, { id: "2", stage: "a" }], "stage");
    expect(g[g.length - 1].key).toBe(UNASSIGNED);
  });
});
