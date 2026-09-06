import { describe, expect, it } from "vitest";

import { buildFormZod, makeDefaultValues, writableFields } from "./form-schema";
import type { FormField, FormSchema } from "./types";

function field(slug: string, over: Partial<FormField> = {}): FormField {
  return {
    slug,
    name: slug,
    field_type: "text",
    description: "",
    is_required: false,
    is_unique: false,
    is_hidden: false,
    is_readonly: false,
    is_system: false,
    default_value: null,
    validation_rules: [],
    config: {},
    order: 0,
    read_roles: [],
    write_roles: [],
    ...over,
  };
}

function schema(fields: FormField[]): FormSchema {
  return {
    entity_slug: "lead",
    entity_name: "Lead",
    form_id: null,
    form_name: "Default",
    layout_type: "sections",
    sections: [],
    fields,
    conditional_rules: [],
  };
}

describe("writableFields", () => {
  it("excludes hidden and backend-computed fields", () => {
    const s = schema([
      field("name"),
      field("secret", { is_hidden: true }),
      field("total", { field_type: "formula" }),
      field("created", { field_type: "created_at" }),
    ]);
    expect(writableFields(s).map((f) => f.slug)).toEqual(["name"]);
  });
});

describe("buildFormZod", () => {
  it("validates only writable fields", () => {
    const s = schema([
      field("name", { is_required: true }),
      field("score", { field_type: "integer" }),
      field("total", { field_type: "formula" }), // read-only → not in the schema
    ]);
    const zod = buildFormZod(s);
    expect("total" in zod.shape).toBe(false);
    expect(zod.safeParse({ name: "", score: "" }).success).toBe(false); // name required
    expect(zod.safeParse({ name: "Acme", score: "" }).success).toBe(true);
  });
});

describe("makeDefaultValues", () => {
  it("uses default_value, else a type-appropriate empty", () => {
    const s = schema([
      field("name", { default_value: "Untitled" }),
      field("active", { field_type: "boolean" }),
      field("tags", { field_type: "multi_select" }),
      field("score", { field_type: "integer" }),
      field("note"),
    ]);
    expect(makeDefaultValues(s)).toEqual({
      name: "Untitled",
      active: false,
      tags: [],
      score: "",
      note: "",
    });
  });

  it("omits read-only fields from defaults", () => {
    const s = schema([field("name"), field("id", { field_type: "uuid" })]);
    expect(Object.keys(makeDefaultValues(s))).toEqual(["name"]);
  });

  it("uses type-appropriate empties across kinds", () => {
    const s = schema([
      field("amount", { field_type: "currency" }),
      field("stars", { field_type: "rating" }),
      field("owners", { field_type: "multi_user" }),
      field("links", { field_type: "multi_lookup" }),
      field("when", { field_type: "date" }),
    ]);
    expect(makeDefaultValues(s)).toEqual({
      amount: "",
      stars: "",
      owners: [],
      links: [],
      when: "",
    });
  });
});
