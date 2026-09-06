/**
 * System-Entity Adapter (B0.2) — PURE adapters that map a B0 descriptor (from
 * `/api/v1/system-entities/{slug}/`) into the SAME `EntityMeta` / `FormSchema` shapes the Generic
 * Runtime already consumes for metadata entities. This is the whole trick: no new components, no
 * per-engine code — the existing DataTable / Form Renderer / Field Registry render native models
 * because they see the identical metadata shape.
 *
 * Domain-agnostic: nothing here knows about treasury/inventory/finance — it reflects an arbitrary
 * descriptor.
 */
import type { EntityMeta, FieldMeta, FormField, FormSchema } from "@/lib/metadata/types";

export interface SystemFieldDescriptor {
  name: string;
  label: string;
  type: string; // text | number | decimal | date | datetime | boolean | select | reference
  readonly: boolean;
  filterable: boolean;
  sortable: boolean;
  choices?: { value: string; label: string }[];
  reference?: string;
}

export interface SystemActionDescriptor {
  key: string;
  label: string;
  method: string;
  path: string;
}

export interface SystemEntityDescriptor {
  slug: string;
  name: string;
  plural_name: string;
  module: string;
  kind: "system";
  fields: SystemFieldDescriptor[];
  actions: SystemActionDescriptor[];
  capabilities: { can_create: boolean; can_update: boolean; can_delete: boolean };
  default_ordering: string;
}

/** Lightweight list item from `/api/v1/system-entities/`. */
export interface SystemEntityListItem {
  slug: string;
  name: string;
  plural_name: string;
  module: string;
  kind: "system";
  can_read: boolean;
  can_create: boolean;
}

/** B0 field type → Generic-Runtime `field_type` (keys the field-type registry already knows). */
export function mapFieldType(t: string): string {
  switch (t) {
    case "number":
      return "number";
    case "decimal":
      return "decimal";
    case "date":
      return "date";
    case "datetime":
      return "datetime";
    case "boolean":
      return "boolean";
    case "select":
      return "select";
    case "reference":
      return "text"; // display the id; true lookup arrives with B0.2 related-records
    default:
      return "text";
  }
}

function toFieldMeta(f: SystemFieldDescriptor, order: number): FieldMeta {
  return {
    id: f.name,
    slug: f.name,
    name: f.label,
    field_type: mapFieldType(f.type),
    is_required: false,
    is_hidden: false,
    is_readonly: f.readonly,
    is_promoted: true,
    is_filterable: f.filterable,
    is_sortable: f.sortable,
    config: f.choices ? { choices: f.choices } : {},
    order,
  };
}

/** Pick a sensible list/title column: first non-readonly text-ish field, else the first field. */
export function titleFieldOf(desc: SystemEntityDescriptor): string {
  const preferred = ["number", "code", "name", "sku", "title"];
  for (const p of preferred) {
    if (desc.fields.some((f) => f.name === p)) return p;
  }
  const firstWritable = desc.fields.find((f) => !f.readonly);
  return firstWritable?.name ?? desc.fields[0]?.name ?? "id";
}

export function descriptorToEntityMeta(desc: SystemEntityDescriptor): EntityMeta {
  return {
    id: desc.slug,
    slug: desc.slug,
    name: desc.name,
    plural_name: desc.plural_name,
    description: "",
    icon: "",
    color: "",
    module: desc.module || null,
    is_active: true,
    title_field_slug: titleFieldOf(desc),
    current_schema_version: 0,
    fields: desc.fields.map(toFieldMeta),
    can_read: true,
    can_create: desc.capabilities.can_create,
    kind: "system",
    capabilities: desc.capabilities,
    actions: desc.actions,
  };
}

function toFormField(f: SystemFieldDescriptor, order: number): FormField {
  return {
    slug: f.name,
    name: f.label,
    field_type: mapFieldType(f.type),
    description: "",
    is_required: false,
    is_unique: false,
    is_hidden: false,
    is_readonly: f.readonly,
    is_system: f.readonly,
    default_value: null,
    validation_rules: [],
    config: f.choices ? { choices: f.choices } : {},
    order,
    read_roles: [],
    write_roles: [],
  };
}

/** Build a create/edit FormSchema from the descriptor — writable fields only, one "main" section. */
export function descriptorToFormSchema(desc: SystemEntityDescriptor): FormSchema {
  const writable = desc.fields.filter((f) => !f.readonly);
  const fields = writable.map(toFormField);
  return {
    entity_slug: desc.slug,
    entity_name: desc.name,
    form_id: null,
    form_name: "Default",
    layout_type: "single",
    sections: [
      { key: "main", title: desc.name, columns: 1, fields: writable.map((f) => f.name), condition: null },
    ],
    fields,
    conditional_rules: [],
  };
}
