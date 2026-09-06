/**
 * Form Builder helpers (Phase F1.8) — pure functions that turn an entity's fields plus an
 * in-progress section layout into a previewable `FormSchema` (fed straight to the Form
 * Renderer), and immutable layout-editing operations (add/remove/move sections + fields).
 * No drag library: ordering is explicit move operations — fully deterministic + testable.
 */
import { isReadOnlyField } from "./field-types";
import type { FieldDef, FormField, FormSchema, FormSection } from "./types";

/** Map a raw FieldDefinition to the FormField shape the renderer consumes. */
export function fieldDefToFormField(f: FieldDef): FormField {
  return {
    slug: f.slug,
    name: f.name,
    field_type: f.field_type,
    description: f.description ?? "",
    is_required: f.is_required,
    is_unique: f.is_unique,
    is_hidden: f.is_hidden,
    is_readonly: f.is_readonly || isReadOnlyField(f),
    is_system: f.is_system,
    default_value: f.default_value,
    validation_rules: [],
    config: f.config ?? {},
    order: f.order,
    read_roles: f.read_roles ?? [],
    write_roles: f.write_roles ?? [],
  };
}

export function emptySection(index: number): FormSection {
  return { key: `section_${index}`, title: `Section ${index + 1}`, columns: 1, fields: [], condition: null };
}

/** Field slugs not placed in any section yet (eligible to add). */
export function unplacedFields(fields: FieldDef[], sections: FormSection[]): FieldDef[] {
  const placed = new Set(sections.flatMap((s) => s.fields));
  return fields.filter((f) => !placed.has(f.slug));
}

/** Build a FormSchema for live preview from the current builder state. */
export function buildPreviewSchema(opts: {
  entitySlug: string;
  entityName: string;
  fields: FieldDef[];
  sections: FormSection[];
  layoutType?: string;
  conditionalRules?: unknown[];
}): FormSchema {
  const bySlug = new Map(opts.fields.map((f) => [f.slug, f]));
  // Only include fields that are actually placed, in placement order.
  const placedSlugs = opts.sections.flatMap((s) => s.fields);
  const formFields: FormField[] = placedSlugs
    .map((slug) => bySlug.get(slug))
    .filter((f): f is FieldDef => !!f)
    .map(fieldDefToFormField);
  return {
    entity_slug: opts.entitySlug,
    entity_name: opts.entityName,
    form_id: null,
    form_name: "Preview",
    layout_type: opts.layoutType ?? "sections",
    sections: opts.sections,
    fields: formFields,
    conditional_rules: opts.conditionalRules ?? [],
  };
}

// ── immutable layout operations ──────────────────────────────────────────────────
function replaceAt<T>(arr: T[], index: number, value: T): T[] {
  const copy = arr.slice();
  copy[index] = value;
  return copy;
}

function swap<T>(arr: T[], i: number, j: number): T[] {
  if (i < 0 || j < 0 || i >= arr.length || j >= arr.length) return arr;
  const copy = arr.slice();
  [copy[i], copy[j]] = [copy[j], copy[i]];
  return copy;
}

export function addSection(sections: FormSection[]): FormSection[] {
  return [...sections, emptySection(sections.length)];
}

export function removeSection(sections: FormSection[], index: number): FormSection[] {
  return sections.filter((_, i) => i !== index);
}

export function moveSection(sections: FormSection[], index: number, dir: -1 | 1): FormSection[] {
  return swap(sections, index, index + dir);
}

export function updateSection(
  sections: FormSection[],
  index: number,
  patch: Partial<FormSection>,
): FormSection[] {
  const s = sections[index];
  if (!s) return sections;
  return replaceAt(sections, index, { ...s, ...patch });
}

export function addFieldToSection(
  sections: FormSection[],
  index: number,
  fieldSlug: string,
): FormSection[] {
  const s = sections[index];
  if (!s || s.fields.includes(fieldSlug)) return sections;
  return replaceAt(sections, index, { ...s, fields: [...s.fields, fieldSlug] });
}

export function removeFieldFromSection(
  sections: FormSection[],
  index: number,
  fieldSlug: string,
): FormSection[] {
  const s = sections[index];
  if (!s) return sections;
  return replaceAt(sections, index, { ...s, fields: s.fields.filter((f) => f !== fieldSlug) });
}

export function moveFieldWithinSection(
  sections: FormSection[],
  index: number,
  fieldIndex: number,
  dir: -1 | 1,
): FormSection[] {
  const s = sections[index];
  if (!s) return sections;
  const moved = swap(s.fields, fieldIndex, fieldIndex + dir);
  if (moved === s.fields) return sections; // out-of-range swap → no change
  return replaceAt(sections, index, { ...s, fields: moved });
}
