import { describe, expect, it } from "vitest";

import { FIELD_TYPES, getFieldType, isReadOnlyField } from "./field-types";
import type { FormField } from "./types";

/** Every backend FIELD_TYPE_CHOICES value (apps/metadata/models.py) must map. */
const BACKEND_FIELD_TYPES = [
  "text", "textarea", "rich_text", "email", "phone", "url",
  "integer", "decimal", "currency", "percent",
  "date", "datetime", "time", "duration",
  "boolean",
  "select", "multi_select", "status",
  "lookup", "multi_lookup", "user", "multi_user",
  "file", "image",
  "formula", "rollup", "count",
  "created_at", "updated_at", "created_by", "updated_by", "auto_number", "uuid",
  "json", "rating", "progress", "location", "barcode",
] as const;

function field(over: Partial<FormField> = {}): FormField {
  return {
    slug: "f",
    name: "F",
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

describe("field-type registry mapping (100%)", () => {
  it("has an entry for every backend field_type", () => {
    for (const t of BACKEND_FIELD_TYPES) {
      expect(FIELD_TYPES[t], `missing registry entry for ${t}`).toBeDefined();
    }
  });

  it("every entry exposes kind + buildZod + format", () => {
    for (const t of BACKEND_FIELD_TYPES) {
      const e = getFieldType(t);
      expect(typeof e.kind).toBe("string");
      expect(typeof e.buildZod).toBe("function");
      expect(typeof e.format).toBe("function");
      // buildZod must produce a usable schema for a default field
      expect(() => e.buildZod(field({ field_type: t })).safeParse("x")).not.toThrow();
    }
  });

  it("falls back to text for unknown types", () => {
    expect(getFieldType("not_a_type").kind).toBe("text");
  });

  it("marks computed/system types read-only", () => {
    for (const t of ["formula", "rollup", "count", "created_at", "updated_at", "auto_number", "uuid"]) {
      expect(getFieldType(t).readOnly).toBe(true);
    }
    expect(getFieldType("text").readOnly).toBe(false);
    expect(isReadOnlyField(field({ field_type: "text", is_readonly: true }))).toBe(true);
    expect(isReadOnlyField(field({ field_type: "formula" }))).toBe(true);
    expect(isReadOnlyField(field({ field_type: "text" }))).toBe(false);
  });
});

describe("Zod builders", () => {
  it("required text rejects empty, accepts content", () => {
    const z = getFieldType("text").buildZod(field({ is_required: true }));
    expect(z.safeParse("").success).toBe(false);
    expect(z.safeParse("hi").success).toBe(true);
  });

  it("optional text accepts empty", () => {
    const z = getFieldType("text").buildZod(field({ is_required: false }));
    expect(z.safeParse("").success).toBe(true);
  });

  it("applies minLength / regex validation rules", () => {
    const z = getFieldType("text").buildZod(
      field({ is_required: true, validation_rules: [{ type: "minLength", value: 3 }] }),
    );
    expect(z.safeParse("ab").success).toBe(false);
    expect(z.safeParse("abc").success).toBe(true);
  });

  it("email type rejects an invalid address", () => {
    const z = getFieldType("email").buildZod(field({ field_type: "email", is_required: true }));
    expect(z.safeParse("nope").success).toBe(false);
    expect(z.safeParse("a@b.com").success).toBe(true);
  });

  it("integer coerces and rejects non-integers", () => {
    const z = getFieldType("integer").buildZod(field({ field_type: "integer", is_required: true }));
    expect(z.safeParse("5").success).toBe(true);
    expect(z.safeParse("5.5").success).toBe(false);
  });

  it("optional number accepts empty string", () => {
    const z = getFieldType("decimal").buildZod(field({ field_type: "decimal" }));
    expect(z.safeParse("").success).toBe(true);
  });

  it("required multiselect rejects empty array", () => {
    const z = getFieldType("multi_select").buildZod(
      field({ field_type: "multi_select", is_required: true }),
    );
    expect(z.safeParse([]).success).toBe(false);
    expect(z.safeParse(["a"]).success).toBe(true);
  });

  it("boolean coerces", () => {
    const z = getFieldType("boolean").buildZod(field({ field_type: "boolean" }));
    expect(z.safeParse(true).success).toBe(true);
  });

  it("applies maxLength and regex rules", () => {
    const max = getFieldType("text").buildZod(
      field({ is_required: true, validation_rules: [{ type: "maxLength", value: 3 }] }),
    );
    expect(max.safeParse("abcd").success).toBe(false);
    const rx = getFieldType("text").buildZod(
      field({ is_required: true, validation_rules: [{ type: "regex", value: "^[A-Z]+$" }] }),
    );
    expect(rx.safeParse("abc").success).toBe(false);
    expect(rx.safeParse("ABC").success).toBe(true);
  });

  it("applies number min/max rules", () => {
    const z = getFieldType("decimal").buildZod(
      field({
        field_type: "decimal",
        is_required: true,
        validation_rules: [{ type: "min", value: 1 }, { type: "max", value: 10 }],
      }),
    );
    expect(z.safeParse("0").success).toBe(false);
    expect(z.safeParse("5").success).toBe(true);
    expect(z.safeParse("11").success).toBe(false);
  });

  it("url type validates via string field; optional string accepts null", () => {
    const url = getFieldType("url").buildZod(
      field({ field_type: "url", is_required: true, validation_rules: [{ type: "url" }] }),
    );
    expect(url.safeParse("notaurl").success).toBe(false);
    expect(url.safeParse("https://x.com").success).toBe(true);
    const opt = getFieldType("text").buildZod(field());
    expect(opt.safeParse(null).success).toBe(true);
  });

  it("optional multiselect defaults to an empty array", () => {
    const z = getFieldType("multi_lookup").buildZod(field({ field_type: "multi_lookup" }));
    expect(z.parse(undefined)).toEqual([]);
  });

  it("ignores malformed validation rules", () => {
    const z = getFieldType("text").buildZod(
      field({ validation_rules: [{ type: "minLength", value: "x" }, { type: "regex", value: "" }] }),
    );
    expect(z.safeParse("anything").success).toBe(true);
  });
});

describe("formatters", () => {
  it("formats by type", () => {
    expect(getFieldType("boolean").format(true, field())).toBe("Yes");
    expect(getFieldType("boolean").format(false, field())).toBe("No");
    expect(getFieldType("multi_select").format(["a", "b"], field())).toBe("a, b");
    expect(getFieldType("json").format({ a: 1 }, field())).toBe('{"a":1}');
    expect(getFieldType("text").format(null, field())).toBe("");
    expect(getFieldType("text").format("x", field())).toBe("x");
  });

  it("json formatter passes strings through and handles empty + circular", () => {
    expect(getFieldType("json").format('{"raw":true}', field())).toBe('{"raw":true}');
    expect(getFieldType("json").format("", field())).toBe("");
    expect(getFieldType("json").format(null, field())).toBe("");
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    expect(() => getFieldType("json").format(circular, field())).not.toThrow();
  });

  it("asList formatter falls back to text for non-arrays", () => {
    expect(getFieldType("multi_select").format("solo", field())).toBe("solo");
  });
});
