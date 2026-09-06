import { describe, expect, it } from "vitest";

import { evaluateHiddenFields, type ConditionalRule } from "./conditional";

const hidden = (rules: ConditionalRule[], values: Record<string, unknown>) =>
  Array.from(evaluateHiddenFields(rules, values)).sort();

describe("evaluateHiddenFields", () => {
  it("returns nothing when there are no rules", () => {
    expect(hidden([], { a: 1 })).toEqual([]);
    expect(hidden(undefined as unknown as ConditionalRule[], {})).toEqual([]);
  });

  it("hide action hides the target when the condition is met", () => {
    const rules: ConditionalRule[] = [
      { field: "type", op: "=", value: "company", action: "hide", target_field: "first_name" },
    ];
    expect(hidden(rules, { type: "company" })).toEqual(["first_name"]);
    expect(hidden(rules, { type: "person" })).toEqual([]);
  });

  it("show action hides the target UNLESS the condition is met", () => {
    const rules: ConditionalRule[] = [
      { field: "has_discount", op: "=", value: "yes", action: "show", target_field: "discount" },
    ];
    expect(hidden(rules, { has_discount: "no" })).toEqual(["discount"]);
    expect(hidden(rules, { has_discount: "yes" })).toEqual([]);
  });

  it("supports multiple targets and defaults action to show", () => {
    const rules: ConditionalRule[] = [
      { field: "vip", op: "not_empty", targets: ["perk_a", "perk_b"] },
    ];
    expect(hidden(rules, { vip: "" })).toEqual(["perk_a", "perk_b"]);
    expect(hidden(rules, { vip: "x" })).toEqual([]);
  });

  it("evaluates comparison operators", () => {
    const mk = (op: string, value: unknown): ConditionalRule[] => [
      { field: "n", op, value, action: "show", target_field: "t" },
    ];
    expect(hidden(mk("=", 5), { n: 5 })).toEqual([]);
    expect(hidden(mk("!=", 5), { n: 6 })).toEqual([]);
    expect(hidden(mk(">", 3), { n: 4 })).toEqual([]);
    expect(hidden(mk(">=", 4), { n: 4 })).toEqual([]);
    expect(hidden(mk("<", 5), { n: 4 })).toEqual([]);
    expect(hidden(mk("<=", 4), { n: 4 })).toEqual([]);
    expect(hidden(mk(">", 3), { n: 2 })).toEqual(["t"]);
  });

  it("evaluates empty / not_empty / in / contains", () => {
    expect(hidden([{ field: "x", op: "empty", action: "show", target_field: "t" }], { x: "" })).toEqual([]);
    expect(hidden([{ field: "x", op: "not_empty", action: "show", target_field: "t" }], { x: "" })).toEqual(["t"]);
    expect(hidden([{ field: "x", op: "in", value: ["a", "b"], action: "show", target_field: "t" }], { x: "a" })).toEqual([]);
    expect(hidden([{ field: "x", op: "contains", value: "a", action: "show", target_field: "t" }], { x: ["a"] })).toEqual([]);
    expect(hidden([{ field: "x", op: "contains", value: "z", action: "show", target_field: "t" }], { x: "abc" })).toEqual(["t"]);
  });

  it("an unknown operator falls back to a presence check", () => {
    const rules: ConditionalRule[] = [{ field: "x", op: "weird", action: "show", target_field: "t" }];
    expect(hidden(rules, { x: "set" })).toEqual([]);
    expect(hidden(rules, { x: "" })).toEqual(["t"]);
  });

  it("ignores malformed rules (no field)", () => {
    expect(hidden([{} as ConditionalRule], { x: 1 })).toEqual([]);
  });

  it("treats empty arrays as empty for not_empty", () => {
    expect(hidden([{ field: "tags", op: "not_empty", action: "show", target_field: "t" }], { tags: [] })).toEqual(["t"]);
  });
});
