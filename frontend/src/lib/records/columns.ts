/**
 * Pure list-column derivation (Phase F1.7) — metadata → table columns, no per-entity code.
 */
import { getFieldType } from "@/lib/metadata/field-types";
import type { EntityMeta, FieldMeta } from "@/lib/metadata/types";

export interface ListColumn {
  slug: string;
  label: string;
  fieldType: string;
  sortable: boolean;
}

const MAX_COLUMNS = 8;

/** Columns for an entity's list/table view: visible fields, title field first, capped. */
export function buildListColumns(entity: EntityMeta, max = MAX_COLUMNS): ListColumn[] {
  const visible = entity.fields
    .filter((f) => !f.is_hidden)
    .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));

  const title = entity.title_field_slug;
  const ordered = [
    ...visible.filter((f) => f.slug === title),
    ...visible.filter((f) => f.slug !== title),
  ];

  return ordered.slice(0, max).map((f) => ({
    slug: f.slug,
    label: f.name,
    fieldType: f.field_type,
    sortable: f.is_sortable ?? false,
  }));
}

/** Format a cell value for display, using the field-type registry's formatter. */
export function formatCell(value: unknown, field: Pick<FieldMeta, "field_type" | "name">): string {
  return getFieldType(field.field_type).format(value, field as never);
}

/** The display title of a record (its title field, falling back to id). */
export function recordTitle(record: Record<string, unknown>, entity: EntityMeta): string {
  const raw = record[entity.title_field_slug];
  if (raw !== null && raw !== undefined && raw !== "") return String(raw);
  return String(record.id ?? "Untitled");
}
