/**
 * Field-type registry (Phase F1.5) — the single source mapping every backend
 * `field_type` → { input kind, read-only?, Zod-builder, display formatter }.
 *
 * One entry per backend `FIELD_TYPE_CHOICES` value. The Form Renderer (F1.6) maps `kind`
 * to a component; lists/detail use `format`; forms compose validation from `buildZod`.
 * Permission-awareness lives in the resolved FormSchema (hidden fields filtered, masked
 * values pre-masked by the backend) — the registry is permission-agnostic.
 */
import { z } from "zod";

import type { FormField, ValidationRule } from "./types";

export type FieldInputKind =
  | "text"
  | "textarea"
  | "richtext"
  | "email"
  | "phone"
  | "url"
  | "number"
  | "currency"
  | "percent"
  | "date"
  | "datetime"
  | "time"
  | "duration"
  | "boolean"
  | "select"
  | "multiselect"
  | "relation"
  | "multirelation"
  | "user"
  | "multiuser"
  | "file"
  | "image"
  | "json"
  | "rating"
  | "progress"
  | "location"
  | "barcode"
  | "readonly";

export interface FieldTypeEntry {
  kind: FieldInputKind;
  /** Always backend-computed → render read-only, exclude from the writable Zod schema. */
  readOnly: boolean;
  buildZod: (field: FormField) => z.ZodTypeAny;
  format: (value: unknown, field: FormField) => string;
}

// ── shared helpers ────────────────────────────────────────────────────────────
function ruleNum(r: ValidationRule): number | null {
  const raw = r.value ?? r.params;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function applyStringRules(schema: z.ZodString, rules: ValidationRule[]): z.ZodString {
  let s = schema;
  for (const r of rules) {
    const n = ruleNum(r);
    if ((r.type === "minLength" || r.type === "min") && n !== null) s = s.min(n, r.message);
    else if ((r.type === "maxLength" || r.type === "max") && n !== null) s = s.max(n, r.message);
    else if (r.type === "regex" || r.type === "pattern") {
      const pat = String(r.value ?? r.params ?? "");
      if (pat) s = s.regex(new RegExp(pat), r.message);
    } else if (r.type === "email") s = s.email(r.message);
    else if (r.type === "url") s = s.url(r.message);
  }
  return s;
}

function applyNumberRules(schema: z.ZodNumber, rules: ValidationRule[]): z.ZodNumber {
  let s = schema;
  for (const r of rules) {
    const n = ruleNum(r);
    if (n === null) continue;
    if (r.type === "min") s = s.min(n, r.message);
    else if (r.type === "max") s = s.max(n, r.message);
  }
  return s;
}

/** Required → non-empty; optional → also accepts "" / null / undefined. */
function stringField(base: z.ZodString, field: FormField): z.ZodTypeAny {
  const withRules = applyStringRules(base, field.validation_rules ?? []);
  if (field.is_required) return withRules.min(1, "This field is required");
  return withRules.or(z.literal("")).nullish();
}

function numberField(field: FormField): z.ZodTypeAny {
  const base = applyNumberRules(z.coerce.number(), field.validation_rules ?? []);
  if (field.is_required) return base;
  return z.preprocess(
    (v) => (v === "" || v === null || v === undefined ? undefined : v),
    base.optional(),
  );
}

function boolField(): z.ZodTypeAny {
  return z.coerce.boolean();
}

function relationField(field: FormField, multi: boolean): z.ZodTypeAny {
  if (multi) {
    const arr = z.array(z.string());
    return field.is_required ? arr.min(1, "Select at least one") : arr.default([]);
  }
  return field.is_required ? z.string().min(1, "This field is required") : z.string().nullish();
}

function readonlyZod(): z.ZodTypeAny {
  return z.any().optional();
}

// ── formatters ────────────────────────────────────────────────────────────────
const asText = (v: unknown): string => (v === null || v === undefined ? "" : String(v));
const asList = (v: unknown): string => (Array.isArray(v) ? v.join(", ") : asText(v));
const asBool = (v: unknown): string => (v === null || v === undefined ? "" : v ? "Yes" : "No");
const asJson = (v: unknown): string => {
  if (v === null || v === undefined || v === "") return "";
  try {
    return typeof v === "string" ? v : JSON.stringify(v);
  } catch {
    return asText(v);
  }
};

// ── entry builders ────────────────────────────────────────────────────────────
const textEntry = (kind: FieldInputKind, fmt = asText): FieldTypeEntry => ({
  kind,
  readOnly: false,
  buildZod: (f) =>
    stringField(kind === "email" ? z.string().email("Enter a valid email") : z.string(), f),
  format: fmt,
});

const numberEntry = (kind: FieldInputKind, fmt = asText): FieldTypeEntry => ({
  kind,
  readOnly: false,
  buildZod: numberField,
  format: fmt,
});

const readonlyEntry = (kind: FieldInputKind, fmt = asText): FieldTypeEntry => ({
  kind,
  readOnly: true,
  buildZod: readonlyZod,
  format: fmt,
});

// ── the registry: one entry per backend field_type ────────────────────────────
export const FIELD_TYPES: Record<string, FieldTypeEntry> = {
  // text
  text: textEntry("text"),
  textarea: textEntry("textarea"),
  rich_text: textEntry("richtext"),
  email: textEntry("email"),
  phone: textEntry("phone"),
  url: { ...textEntry("url"), buildZod: (f) => stringField(z.string(), f) },
  // numbers
  integer: { ...numberEntry("number"), buildZod: (f) => (f.is_required ? z.coerce.number().int() : numberField(f)) },
  decimal: numberEntry("number"),
  currency: numberEntry("currency"),
  percent: numberEntry("percent"),
  // date/time
  date: textEntry("date"),
  datetime: textEntry("datetime"),
  time: textEntry("time"),
  duration: numberEntry("duration"),
  // boolean
  boolean: { kind: "boolean", readOnly: false, buildZod: boolField, format: asBool },
  // select
  select: textEntry("select"),
  status: textEntry("select"),
  multi_select: {
    kind: "multiselect",
    readOnly: false,
    buildZod: (f) => relationField(f, true),
    format: asList,
  },
  // relational
  lookup: { kind: "relation", readOnly: false, buildZod: (f) => relationField(f, false), format: asText },
  multi_lookup: {
    kind: "multirelation",
    readOnly: false,
    buildZod: (f) => relationField(f, true),
    format: asList,
  },
  user: { kind: "user", readOnly: false, buildZod: (f) => relationField(f, false), format: asText },
  multi_user: {
    kind: "multiuser",
    readOnly: false,
    buildZod: (f) => relationField(f, true),
    format: asList,
  },
  // files
  file: { kind: "file", readOnly: false, buildZod: (f) => relationField(f, false), format: asText },
  image: { kind: "image", readOnly: false, buildZod: (f) => relationField(f, false), format: asText },
  // computed / system (read-only)
  formula: readonlyEntry("readonly"),
  rollup: readonlyEntry("readonly"),
  count: readonlyEntry("readonly"),
  created_at: readonlyEntry("readonly"),
  updated_at: readonlyEntry("readonly"),
  created_by: readonlyEntry("readonly"),
  updated_by: readonlyEntry("readonly"),
  auto_number: readonlyEntry("readonly"),
  uuid: readonlyEntry("readonly"),
  // special
  json: { kind: "json", readOnly: false, buildZod: (f) => (f.is_required ? z.any() : z.any().optional()), format: asJson },
  rating: numberEntry("rating"),
  progress: numberEntry("progress"),
  location: textEntry("location"),
  barcode: textEntry("barcode"),
};

const FALLBACK: FieldTypeEntry = textEntry("text");

/** Resolve a registry entry; unknown types fall back to a plain text field. */
export function getFieldType(fieldType: string): FieldTypeEntry {
  return FIELD_TYPES[fieldType] ?? FALLBACK;
}

/** Is this field backend-computed (never user-writable)? */
export function isReadOnlyField(field: Pick<FormField, "field_type" | "is_readonly">): boolean {
  return field.is_readonly || getFieldType(field.field_type).readOnly;
}
