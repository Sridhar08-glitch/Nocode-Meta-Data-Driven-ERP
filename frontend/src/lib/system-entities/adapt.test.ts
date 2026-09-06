import { describe, expect, it } from "vitest";

import {
  descriptorToEntityMeta,
  descriptorToFormSchema,
  mapFieldType,
  type SystemEntityDescriptor,
  titleFieldOf,
} from "./adapt";

const DESC: SystemEntityDescriptor = {
  slug: "treasury_facility",
  name: "Facility",
  plural_name: "Facilities",
  module: "treasury",
  kind: "system",
  default_ordering: "-created_at",
  capabilities: { can_create: true, can_update: false, can_delete: false },
  actions: [{ key: "drawdown", label: "Drawdown", method: "POST", path: "/api/v1/treasury/facilities/{id}/drawdown/" }],
  fields: [
    { name: "id", label: "Id", type: "text", readonly: true, filterable: true, sortable: true },
    { name: "number", label: "Number", type: "text", readonly: false, filterable: true, sortable: true },
    { name: "principal", label: "Principal", type: "decimal", readonly: false, filterable: true, sortable: true },
    { name: "rate_type", label: "Rate Type", type: "select", readonly: false, filterable: true, sortable: true, choices: [{ value: "fixed", label: "Fixed" }] },
    { name: "maturity_date", label: "Maturity", type: "date", readonly: false, filterable: true, sortable: true },
    { name: "counterparty_id", label: "Counterparty", type: "reference", readonly: false, filterable: true, sortable: true, reference: "treasurycounterparty" },
  ],
};

describe("mapFieldType", () => {
  it("maps B0 types to runtime field_types", () => {
    expect(mapFieldType("decimal")).toBe("decimal");
    expect(mapFieldType("date")).toBe("date");
    expect(mapFieldType("datetime")).toBe("datetime");
    expect(mapFieldType("boolean")).toBe("boolean");
    expect(mapFieldType("select")).toBe("select");
    expect(mapFieldType("number")).toBe("number");
    expect(mapFieldType("reference")).toBe("text"); // id display until B0.2 related-records
    expect(mapFieldType("anything-else")).toBe("text");
  });
});

describe("titleFieldOf", () => {
  it("prefers number/code/name over arbitrary fields", () => {
    expect(titleFieldOf(DESC)).toBe("number");
  });
});

describe("descriptorToEntityMeta", () => {
  const meta = descriptorToEntityMeta(DESC);
  it("carries identity + kind + capabilities + actions", () => {
    expect(meta.slug).toBe("treasury_facility");
    expect(meta.plural_name).toBe("Facilities");
    expect(meta.kind).toBe("system");
    expect(meta.can_create).toBe(true);
    expect(meta.actions?.[0].key).toBe("drawdown");
    expect(meta.title_field_slug).toBe("number");
  });
  it("maps fields with types + readonly + choices", () => {
    const byName = Object.fromEntries(meta.fields.map((f) => [f.slug, f]));
    expect(byName.principal.field_type).toBe("decimal");
    expect(byName.rate_type.field_type).toBe("select");
    expect(byName.rate_type.config.choices).toBeDefined();
    expect(byName.id.is_readonly).toBe(true);
  });
});

describe("descriptorToFormSchema", () => {
  const form = descriptorToFormSchema(DESC);
  it("includes only writable fields in one section", () => {
    const names = form.fields.map((f) => f.slug);
    expect(names).not.toContain("id"); // readonly excluded
    expect(names).toContain("number");
    expect(names).toContain("principal");
    expect(form.sections).toHaveLength(1);
    expect(form.sections[0].fields).toEqual(names);
  });
});
