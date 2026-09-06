import { describe, expect, it } from "vitest";

import {
  addFieldToSection,
  addSection,
  buildPreviewSchema,
  emptySection,
  fieldDefToFormField,
  moveFieldWithinSection,
  moveSection,
  removeFieldFromSection,
  removeSection,
  unplacedFields,
  updateSection,
} from "./form-builder";
import type { FieldDef, FormSection } from "./types";

function field(slug: string, over: Partial<FieldDef> = {}): FieldDef {
  return {
    id: slug,
    slug,
    name: slug,
    field_type: "text",
    description: "",
    is_promoted: false,
    column_name: "",
    is_filterable: true,
    is_sortable: true,
    is_searchable: false,
    has_index: false,
    is_required: false,
    is_unique: false,
    default_value: null,
    is_system: false,
    is_hidden: false,
    is_readonly: false,
    order: 0,
    config: {},
    read_roles: [],
    write_roles: [],
    ...over,
  };
}

describe("fieldDefToFormField", () => {
  it("maps and flags computed types read-only", () => {
    const ff = fieldDefToFormField(field("created", { field_type: "formula" }));
    expect(ff.is_readonly).toBe(true);
    expect(ff.validation_rules).toEqual([]);
  });

  it("preserves an explicit readonly flag and config/roles", () => {
    const ff = fieldDefToFormField(
      field("x", { is_readonly: true, config: { a: 1 }, read_roles: ["admin"] }),
    );
    expect(ff.is_readonly).toBe(true);
    expect(ff.config).toEqual({ a: 1 });
    expect(ff.read_roles).toEqual(["admin"]);
  });

  it("leaves an ordinary editable field writable", () => {
    const ff = fieldDefToFormField(field("name", { field_type: "text" }));
    expect(ff.is_readonly).toBe(false);
  });

  it("defaults nullish description/config/roles", () => {
    const raw = {
      ...field("y"),
      description: undefined,
      config: undefined,
      read_roles: undefined,
      write_roles: undefined,
    } as unknown as FieldDef;
    const ff = fieldDefToFormField(raw);
    expect(ff.description).toBe("");
    expect(ff.config).toEqual({});
    expect(ff.read_roles).toEqual([]);
    expect(ff.write_roles).toEqual([]);
  });
});

describe("unplacedFields", () => {
  it("returns only fields not in any section", () => {
    const fields = [field("a"), field("b"), field("c")];
    const sections: FormSection[] = [
      { key: "s", title: "S", columns: 1, fields: ["a"], condition: null },
    ];
    expect(unplacedFields(fields, sections).map((f) => f.slug)).toEqual(["b", "c"]);
  });
});

describe("buildPreviewSchema", () => {
  it("includes only placed fields in placement order", () => {
    const fields = [field("a"), field("b"), field("c")];
    const sections: FormSection[] = [
      { key: "s1", title: "One", columns: 2, fields: ["c", "a"], condition: null },
    ];
    const schema = buildPreviewSchema({
      entitySlug: "lead",
      entityName: "Lead",
      fields,
      sections,
    });
    expect(schema.fields.map((f) => f.slug)).toEqual(["c", "a"]);
    expect(schema.layout_type).toBe("sections");
    expect(schema.form_id).toBeNull();
    expect(schema.entity_slug).toBe("lead");
  });

  it("ignores section slugs with no matching field and honours layout_type", () => {
    const schema = buildPreviewSchema({
      entitySlug: "lead",
      entityName: "Lead",
      fields: [field("a")],
      sections: [{ key: "s", title: "S", columns: 1, fields: ["a", "ghost"], condition: null }],
      layoutType: "wizard",
    });
    expect(schema.fields.map((f) => f.slug)).toEqual(["a"]);
    expect(schema.layout_type).toBe("wizard");
  });
});

describe("layout operations (immutable)", () => {
  const base: FormSection[] = [emptySection(0), emptySection(1)];

  it("addSection appends with the next index", () => {
    const next = addSection(base);
    expect(next).toHaveLength(3);
    expect(next[2].key).toBe("section_2");
    expect(base).toHaveLength(2); // unchanged
  });

  it("removeSection drops by index", () => {
    expect(removeSection(base, 0)).toHaveLength(1);
    expect(removeSection(base, 0)[0].key).toBe("section_1");
  });

  it("moveSection swaps, no-op at the edges", () => {
    expect(moveSection(base, 0, 1)[0].key).toBe("section_1");
    expect(moveSection(base, 0, -1)).toBe(base); // out of range → same ref
    expect(moveSection(base, 1, 1)).toBe(base);
  });

  it("updateSection patches a section, no-op for bad index", () => {
    expect(updateSection(base, 0, { title: "Renamed" })[0].title).toBe("Renamed");
    expect(updateSection(base, 9, { title: "x" })).toBe(base);
  });

  it("addFieldToSection adds once (dedup)", () => {
    const one = addFieldToSection(base, 0, "a");
    expect(one[0].fields).toEqual(["a"]);
    expect(addFieldToSection(one, 0, "a")).toBe(one); // duplicate → same ref
  });

  it("removeFieldFromSection removes a placed field, no-op for bad index", () => {
    const withField = addFieldToSection(base, 0, "a");
    expect(removeFieldFromSection(withField, 0, "a")[0].fields).toEqual([]);
    expect(removeFieldFromSection(withField, 9, "a")).toBe(withField); // bad index → same ref
  });

  it("addFieldToSection no-ops for a bad index", () => {
    expect(addFieldToSection(base, 9, "a")).toBe(base);
  });

  it("moveFieldWithinSection reorders fields, no-op for edges and bad index", () => {
    let s = addFieldToSection(base, 0, "a");
    s = addFieldToSection(s, 0, "b");
    expect(moveFieldWithinSection(s, 0, 0, 1)[0].fields).toEqual(["b", "a"]);
    expect(moveFieldWithinSection(s, 0, 0, -1)).toBe(s); // edge no-op
    expect(moveFieldWithinSection(s, 9, 0, 1)).toBe(s); // bad section index → same ref
  });
});
