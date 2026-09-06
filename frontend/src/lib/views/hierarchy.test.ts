import { describe, expect, it } from "vitest";

import { buildForest, flattenForest } from "./hierarchy";

describe("buildForest", () => {
  it("builds a parent→children tree with depths", () => {
    const rows = [
      { id: "1", parent: null },
      { id: "2", parent: "1" },
      { id: "3", parent: "1" },
      { id: "4", parent: "2" },
    ];
    const forest = buildForest(rows, "parent");
    expect(forest).toHaveLength(1);
    expect(forest[0].row.id).toBe("1");
    expect(forest[0].depth).toBe(0);
    expect(forest[0].children.map((c) => c.row.id)).toEqual(["2", "3"]);
    expect(forest[0].children[0].children[0].row.id).toBe("4");
    expect(forest[0].children[0].children[0].depth).toBe(2);
  });

  it("treats orphans (missing parent) as roots", () => {
    const forest = buildForest([{ id: "1", parent: "ghost" }, { id: "2", parent: null }], "parent");
    expect(forest.map((n) => n.row.id).sort()).toEqual(["1", "2"]);
  });

  it("protects against cycles (self + mutual) by promoting to roots", () => {
    const selfCycle = buildForest([{ id: "1", parent: "1" }], "parent");
    expect(selfCycle).toHaveLength(1);
    const mutual = buildForest(
      [{ id: "a", parent: "b" }, { id: "b", parent: "a" }],
      "parent",
    );
    // neither can nest under the other without looping → both roots
    expect(mutual).toHaveLength(2);
  });

  it("flattens depth-first", () => {
    const rows = [
      { id: "1", parent: null },
      { id: "2", parent: "1" },
      { id: "3", parent: null },
    ];
    expect(flattenForest(buildForest(rows, "parent")).map((n) => n.row.id)).toEqual(["1", "2", "3"]);
  });
});
