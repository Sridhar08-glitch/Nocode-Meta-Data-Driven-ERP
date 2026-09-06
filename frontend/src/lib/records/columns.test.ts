import { describe, expect, it } from "vitest";

import type { EntityMeta, FieldMeta } from "@/lib/metadata/types";

import { buildListColumns, formatCell, recordTitle } from "./columns";

function fld(slug: string, over: Partial<FieldMeta> = {}): FieldMeta {
  return {
    id: slug,
    slug,
    name: slug.toUpperCase(),
    field_type: "text",
    is_required: false,
    is_hidden: false,
    is_readonly: false,
    config: {},
    order: 0,
    ...over,
  };
}

function entity(fields: FieldMeta[], over: Partial<EntityMeta> = {}): EntityMeta {
  return {
    id: "e",
    slug: "lead",
    name: "Lead",
    plural_name: "Leads",
    description: "",
    icon: "",
    color: "",
    module: null,
    is_active: true,
    title_field_slug: "name",
    current_schema_version: 1,
    fields,
    ...over,
  };
}

describe("buildListColumns", () => {
  it("puts the title field first and skips hidden fields", () => {
    const cols = buildListColumns(
      entity([
        fld("status", { order: 1 }),
        fld("name", { order: 2 }),
        fld("secret", { is_hidden: true, order: 3 }),
      ]),
    );
    expect(cols.map((c) => c.slug)).toEqual(["name", "status"]);
  });

  it("marks sortable columns from the field flag", () => {
    const cols = buildListColumns(entity([fld("name", { is_sortable: true })]));
    expect(cols[0].sortable).toBe(true);
  });

  it("caps the number of columns", () => {
    const many = Array.from({ length: 12 }, (_, i) => fld(`f${i}`, { order: i }));
    expect(buildListColumns(entity(many, { title_field_slug: "f0" }), 5)).toHaveLength(5);
  });
});

describe("formatCell", () => {
  it("formats via the field-type registry", () => {
    expect(formatCell(true, { field_type: "boolean", name: "Active" })).toBe("Yes");
    expect(formatCell(["a", "b"], { field_type: "multi_select", name: "Tags" })).toBe("a, b");
  });
});

describe("recordTitle", () => {
  it("uses the title field, falling back to id", () => {
    const e = entity([fld("name")]);
    expect(recordTitle({ name: "Acme", id: "1" }, e)).toBe("Acme");
    expect(recordTitle({ name: "", id: "1" }, e)).toBe("1");
    expect(recordTitle({ id: "x" }, e)).toBe("x");
  });
});
