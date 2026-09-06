import { describe, expect, it } from "vitest";

import { FIELD_TYPE_GROUPS, FIELD_TYPE_LABELS, isValidSlug, slugify } from "./slug";

describe("slugify", () => {
  it("lowercases and underscores", () => {
    expect(slugify("First Name")).toBe("first_name");
    expect(slugify("  Account #1!  ")).toBe("account_1");
  });
  it("collapses repeats and trims underscores", () => {
    expect(slugify("a---b___c")).toBe("a_b_c");
  });
  it("prefixes when it doesn't start with a letter", () => {
    expect(slugify("123 abc")).toBe("f_123_abc");
    expect(slugify("___")).toBe("f_");
  });
  it("caps at 63 chars", () => {
    expect(slugify("a".repeat(100)).length).toBe(63);
  });
});

describe("isValidSlug", () => {
  it("accepts valid slugs", () => {
    expect(isValidSlug("lead")).toBe(true);
    expect(isValidSlug("a_b_2")).toBe(true);
  });
  it("rejects invalid slugs", () => {
    expect(isValidSlug("1lead")).toBe(false);
    expect(isValidSlug("Lead")).toBe(false);
    expect(isValidSlug("a-b")).toBe(false);
    expect(isValidSlug("")).toBe(false);
  });
});

describe("field-type catalog", () => {
  it("labels cover every grouped type", () => {
    const all = FIELD_TYPE_GROUPS.flatMap((g) => g.types);
    expect(all.length).toBeGreaterThan(20);
    expect(FIELD_TYPE_LABELS.text).toBe("Text");
    expect(FIELD_TYPE_LABELS.lookup).toBe("Lookup");
  });
});
