/**
 * FormSchema → Zod + defaults (Phase F1.5).
 *
 * Composes a runtime Zod object for a resolved FormSchema (skipping hidden + backend-
 * computed fields, which are never submitted) and derives initial RHF values. The Form
 * Renderer (F1.6) consumes both. Pure + unit-tested.
 */
import { z } from "zod";

import { getFieldType, isReadOnlyField } from "./field-types";
import type { FormField, FormSchema } from "./types";

/** Fields the user can edit (visible + not backend-computed). */
export function writableFields(schema: FormSchema): FormField[] {
  return schema.fields.filter((f) => !f.is_hidden && !isReadOnlyField(f));
}

export function buildFormZod(schema: FormSchema) {
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const field of writableFields(schema)) {
    shape[field.slug] = getFieldType(field.field_type).buildZod(field);
  }
  return z.object(shape);
}

function emptyFor(field: FormField): unknown {
  const kind = getFieldType(field.field_type).kind;
  switch (kind) {
    case "boolean":
      return false;
    case "multiselect":
    case "multirelation":
    case "multiuser":
      return [];
    case "number":
    case "currency":
    case "percent":
    case "duration":
    case "rating":
    case "progress":
      return "";
    default:
      return "";
  }
}

/** Initial RHF values: each writable field's default_value, else a type-appropriate empty. */
export function makeDefaultValues(schema: FormSchema): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  for (const field of writableFields(schema)) {
    values[field.slug] =
      field.default_value !== null && field.default_value !== undefined
        ? field.default_value
        : emptyFor(field);
  }
  return values;
}
