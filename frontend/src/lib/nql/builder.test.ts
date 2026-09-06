import { describe, expect, it } from "vitest";

import {
  addToGroup,
  describe as describeQuery,
  emptyCondition,
  emptyGroup,
  emptyQuery,
  getNodeAt,
  normalizeCondition,
  removeAt,
  serialize,
  setGroupOp,
  updateCondition,
  validate,
} from "./builder";
import {
  COMPARISON_OPTIONS,
  type Condition,
  type FilterGroup,
  isGroup,
  isListOp,
  isNullaryOp,
  type NqlQuery,
} from "./types";

describe("type guards & metadata", () => {
  it("identifies groups, nullary and list ops", () => {
    expect(isGroup(emptyGroup())).toBe(true);
    expect(isGroup(emptyCondition("x"))).toBe(false);
    expect(isNullaryOp("is null")).toBe(true);
    expect(isNullaryOp("=")).toBe(false);
    expect(isListOp("in")).toBe(true);
    expect(isListOp("not in")).toBe(true);
    expect(isListOp("=")).toBe(false);
  });

  it("exposes every comparison operator as an option", () => {
    expect(COMPARISON_OPTIONS).toHaveLength(11);
    expect(COMPARISON_OPTIONS.map((o) => o.value)).toContain("contains");
  });
});

describe("constructors", () => {
  it("builds an empty query, group and condition", () => {
    expect(emptyQuery("deals")).toEqual({
      entity: "deals",
      select: [],
      filter: { op: "and", conditions: [] },
      sort: [],
      groupBy: [],
      aggregations: [],
    });
    expect(emptyGroup("or")).toEqual({ op: "or", conditions: [] });
    expect(emptyCondition()).toEqual({ field: "", op: "=", value: "" });
    expect(emptyCondition("status").field).toBe("status");
  });
});

describe("filter-tree edits", () => {
  function tree(): FilterGroup {
    return {
      op: "and",
      conditions: [
        { field: "status", op: "=", value: "open" },
        { op: "or", conditions: [{ field: "value", op: ">", value: 10 }] },
      ],
    };
  }

  it("getNodeAt resolves nested paths and rejects bad ones", () => {
    const root = tree();
    expect(getNodeAt(root, [])).toBe(root);
    expect((getNodeAt(root, [0]) as Condition).field).toBe("status");
    expect((getNodeAt(root, [1, 0]) as Condition).field).toBe("value");
    expect(getNodeAt(root, [9])).toBeUndefined(); // out of range
    expect(getNodeAt(root, [0, 0])).toBeUndefined(); // descend into a leaf
    expect(getNodeAt(root, [9, 0])).toBeUndefined(); // node becomes undefined mid-traversal
  });

  it("edits ignore negative indices", () => {
    const root = tree();
    expect(addToGroup(root, [-1], emptyCondition("x"))).toBe(root);
  });

  it("addToGroup appends to the addressed group (root and nested)", () => {
    const root = tree();
    const next = addToGroup(root, [], emptyCondition("owner"));
    expect((next as FilterGroup).conditions).toHaveLength(3);
    const nested = addToGroup(root, [1], emptyCondition("amount"));
    expect(((nested as FilterGroup).conditions[1] as FilterGroup).conditions).toHaveLength(2);
    expect(root.conditions).toHaveLength(2); // original untouched
  });

  it("addToGroup is a no-op when the path points at a leaf or escapes", () => {
    const root = tree();
    expect(addToGroup(root, [0], emptyCondition("x"))).toEqual(root); // leaf target
    expect(addToGroup(root, [5], emptyCondition("x"))).toBe(root); // out of range
  });

  it("removeAt drops a child, leaves the root, ignores leaf parents", () => {
    const root = tree();
    expect((removeAt(root, [0]) as FilterGroup).conditions).toHaveLength(1);
    expect((removeAt(root, [1, 0]) as FilterGroup).conditions[1]).toEqual({
      op: "or",
      conditions: [],
    });
    expect(removeAt(root, [])).toBe(root); // cannot remove root
    expect(removeAt(root, [0, 0])).toEqual(root); // parent path lands on a leaf → no-op
  });

  it("setGroupOp flips AND/OR and ignores leaves", () => {
    const root = tree();
    expect((setGroupOp(root, [], "or") as FilterGroup).op).toBe("or");
    expect(((setGroupOp(root, [1], "and") as FilterGroup).conditions[1] as FilterGroup).op).toBe(
      "and",
    );
    expect(setGroupOp(root, [0], "or")).toEqual(root); // leaf untouched
  });

  it("updateCondition patches leaves and re-normalises by operator", () => {
    const root = tree();
    const renamed = updateCondition(root, [0], { field: "stage" });
    expect((renamed as FilterGroup).conditions[0]).toEqual({
      field: "stage",
      op: "=",
      value: "open",
    });
    // switching to a nullary op drops the value
    const nullified = updateCondition(root, [0], { op: "is null" });
    expect((nullified as FilterGroup).conditions[0]).toEqual({ field: "status", op: "is null" });
    // group target is left alone
    expect(updateCondition(root, [1], { field: "x" })).toEqual(root);
    // descending past a leaf is a no-op (path overshoots a non-group)
    expect(updateCondition(root, [0, 0], { field: "z" })).toEqual(root);
  });
});

describe("normalizeCondition", () => {
  it("drops value for nullary ops", () => {
    expect(normalizeCondition({ field: "x", op: "is not null", value: "junk" })).toEqual({
      field: "x",
      op: "is not null",
    });
  });
  it("coerces list-op values to arrays", () => {
    expect(normalizeCondition({ field: "x", op: "in", value: "a" }).value).toEqual(["a"]);
    expect(normalizeCondition({ field: "x", op: "in", value: ["a", "b"] }).value).toEqual(["a", "b"]);
    expect(normalizeCondition({ field: "x", op: "in", value: "" }).value).toEqual([]);
    expect(normalizeCondition({ field: "x", op: "not in", value: undefined }).value).toEqual([]);
  });
  it("passes comparison ops through unchanged", () => {
    const c: Condition = { field: "x", op: "=", value: 5 };
    expect(normalizeCondition(c)).toEqual(c);
  });
});

describe("serialize", () => {
  it("omits empty clauses and prunes incomplete filter nodes", () => {
    expect(serialize(emptyQuery("deals"))).toEqual({ entity: "deals" });
  });

  it("keeps populated clauses and normalises conditions", () => {
    const q: NqlQuery = {
      entity: "deals",
      select: ["name", "value"],
      filter: {
        op: "and",
        conditions: [
          { field: "status", op: "in", value: "open" },
          { field: "", op: "=", value: "dropme" }, // incomplete → pruned
          { op: "or", conditions: [] }, // empty group → pruned
          { op: "or", conditions: [{ field: "owner", op: "=", value: "@me" }] },
        ],
      },
      sort: [{ field: "value", direction: "desc" }],
      groupBy: ["status"],
      aggregations: [
        { func: "sum", field: "value", alias: "total" },
        { func: "count" },
      ],
      pagination: { limit: 50, offset: 0 },
      asOf: "2026-01-01",
    };
    const wire = serialize(q);
    expect(wire).toEqual({
      entity: "deals",
      select: ["name", "value"],
      filter: {
        op: "and",
        conditions: [
          { field: "status", op: "in", value: ["open"] },
          { op: "or", conditions: [{ field: "owner", op: "=", value: "@me" }] },
        ],
      },
      sort: [{ field: "value", direction: "desc" }],
      groupBy: ["status"],
      aggregations: [{ func: "sum", field: "value", alias: "total" }, { func: "count" }],
      pagination: { limit: 50, offset: 0 },
      asOf: "2026-01-01",
    });
  });

  it("drops a filter that prunes down to nothing and an empty pagination", () => {
    const q: NqlQuery = {
      entity: "deals",
      filter: { op: "and", conditions: [{ field: "", op: "=", value: "" }] },
      pagination: {},
    };
    expect(serialize(q)).toEqual({ entity: "deals" });
  });

  it("keeps page-based pagination", () => {
    expect(serialize({ entity: "x", pagination: { page: 2 } }).pagination).toEqual({ page: 2 });
  });

  it("is idempotent (round-trips)", () => {
    const built = addToGroup(
      addToGroup(emptyQuery("deals").filter!, [], { field: "status", op: "=", value: "open" }),
      [],
      { op: "or", conditions: [{ field: "value", op: ">=", value: 1000 }] },
    );
    const q: NqlQuery = { ...emptyQuery("deals"), filter: built, sort: [{ field: "name", direction: "asc" }] };
    const once = serialize(q);
    const twice = serialize(once);
    expect(twice).toEqual(once);
  });
});

describe("validate", () => {
  it("flags a missing entity", () => {
    expect(validate({ entity: "" })).toContain("An entity is required.");
  });
  it("flags incomplete conditions and empty list values", () => {
    const errs = validate({
      entity: "deals",
      filter: {
        op: "and",
        conditions: [
          { field: "", op: "=", value: "" },
          { field: "status", op: "in", value: [] },
        ],
      },
    });
    expect(errs).toContain("A filter condition is missing its field.");
    expect(errs.some((e) => e.includes("needs at least one value"))).toBe(true);
  });
  it("flags an aggregation without a field (except count)", () => {
    expect(validate({ entity: "d", aggregations: [{ func: "sum" }] })).toContain(
      'Aggregation "sum" needs a field.',
    );
    expect(validate({ entity: "d", aggregations: [{ func: "count" }] })).toEqual([]);
  });
  it("passes a well-formed query", () => {
    expect(
      validate({
        entity: "deals",
        filter: { op: "and", conditions: [{ field: "status", op: "=", value: "open" }] },
      }),
    ).toEqual([]);
  });
});

describe("describe (view as NQL)", () => {
  it("renders SELECT * with no clauses", () => {
    expect(describeQuery(emptyQuery("deals"))).toBe("SELECT * FROM deals");
  });
  it("renders the unknown-entity placeholder", () => {
    expect(describeQuery({ entity: "" })).toBe("SELECT * FROM ?");
  });
  it("renders columns, where, group, order, limit and offset", () => {
    const q: NqlQuery = {
      entity: "deals",
      select: ["name"],
      filter: {
        op: "and",
        conditions: [
          { field: "status", op: "in", value: ["open", "won"] },
          { field: "owner", op: "=", value: "@me" },
          { field: "closed", op: "is null" },
          { field: "value", op: ">=", value: 1000 },
        ],
      },
      groupBy: ["status"],
      sort: [{ field: "value", direction: "desc" }],
      pagination: { limit: 25, offset: 50 },
    };
    expect(describeQuery(q)).toBe(
      "SELECT name FROM deals WHERE (status in ('open', 'won') AND owner = @me AND closed is null AND value >= 1000) GROUP BY status ORDER BY value DESC LIMIT 25 OFFSET 50",
    );
  });
  it("collapses a single-condition group and renders aggregations", () => {
    expect(
      describeQuery({
        entity: "deals",
        filter: { op: "and", conditions: [{ field: "status", op: "=", value: "open" }] },
        aggregations: [{ func: "sum", field: "value" }, { func: "count" }],
      }),
    ).toBe("SELECT sum(value), count(*) FROM deals WHERE status = 'open'");
  });
  it("renders a null value placeholder and an empty group as no WHERE", () => {
    expect(
      describeQuery({
        entity: "d",
        filter: { op: "and", conditions: [{ field: "x", op: "=", value: null }] },
      }),
    ).toBe("SELECT * FROM d WHERE x = ''");
    expect(describeQuery({ entity: "d", filter: { op: "and", conditions: [] } })).toBe(
      "SELECT * FROM d",
    );
  });
  it("keeps select columns alongside no aggregations", () => {
    expect(describeQuery({ entity: "d", select: ["a", "b"] })).toBe("SELECT a, b FROM d");
  });

  it("drops a group whose children all render empty, and an empty-field leaf", () => {
    expect(
      describeQuery({
        entity: "d",
        filter: {
          op: "and",
          conditions: [
            { field: "", op: "=", value: "" },
            { op: "or", conditions: [{ field: "", op: "=", value: "" }] },
          ],
        },
      }),
    ).toBe("SELECT * FROM d");
  });
});
