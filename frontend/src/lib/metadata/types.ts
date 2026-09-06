/** Metadata shapes (Phase F1.4/F1.5). Hand-typed: these endpoints' generated types are
 *  imprecise (dynamic APIViews), and we add view-level fields like `can_read`. */

export interface ModuleMeta {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  color: string;
  is_active: boolean;
  order: number;
}

export interface FieldMeta {
  id: string;
  slug: string;
  name: string;
  field_type: string;
  is_required: boolean;
  is_hidden: boolean;
  is_readonly: boolean;
  is_promoted?: boolean;
  is_filterable?: boolean;
  is_sortable?: boolean;
  config: Record<string, unknown>;
  order: number;
}

/** A validation rule from `FieldDefinition.validation_rules` ([{type, params, message}]). */
export interface ValidationRule {
  type: string;
  params?: unknown;
  value?: unknown;
  message?: string;
}

/** A field as served by the resolved FormSchema (backend §1.26 `_field_payload`). */
export interface FormField {
  slug: string;
  name: string;
  field_type: string;
  description: string;
  is_required: boolean;
  is_unique: boolean;
  is_hidden: boolean;
  is_readonly: boolean;
  is_system: boolean;
  default_value: unknown;
  validation_rules: ValidationRule[];
  config: Record<string, unknown>;
  order: number;
  read_roles: string[];
  write_roles: string[];
}

export interface FormSection {
  key: string;
  title: string;
  columns: number;
  fields: string[];
  condition: unknown;
}

/** The canonical FormSchema from `GET /metadata/entities/{slug}/form-schema/` (§1.26). */
export interface FormSchema {
  entity_slug: string;
  entity_name: string;
  form_id: string | null;
  form_name: string;
  layout_type: string;
  sections: FormSection[];
  fields: FormField[];
  conditional_rules: unknown[];
}

export interface EntityMeta {
  id: string;
  slug: string;
  name: string;
  plural_name: string;
  description: string;
  icon: string;
  color: string;
  module: string | null;
  is_active: boolean;
  title_field_slug: string;
  current_schema_version: number;
  fields: FieldMeta[];
  /** Per-member RBAC, annotated by the entities endpoint (F1.4). */
  can_read?: boolean;
  can_create?: boolean;
  /** Source discriminator (B0.2). Absent/"metadata" = a metadata EntityDefinition; "system" = a
   *  native-model engine published via the System-Entity Adapter. */
  kind?: "metadata" | "system";
  /** System-entity write capabilities + lifecycle actions (B0.2; present only when kind==="system"). */
  capabilities?: { can_create: boolean; can_update: boolean; can_delete: boolean };
  actions?: { key: string; label: string; method: string; path: string }[];
}

// ── Builder write shapes (Phase F1.8) ──────────────────────────────────────────

/** Body for `POST /metadata/entities/` (CreateEntitySerializer). */
export interface EntityCreate {
  slug: string;
  name: string;
  plural_name: string;
  description?: string;
  title_field_slug?: string;
  settings?: Record<string, unknown>;
}

/** Body for `PATCH /metadata/entities/{slug}/` (EntityUpdateSerializer). */
export interface EntityUpdate {
  name?: string;
  plural_name?: string;
  description?: string;
  title_field_slug?: string;
  settings?: Record<string, unknown>;
  is_active?: boolean;
  icon?: string;
  color?: string;
}

/** Body for `POST /metadata/entities/{slug}/fields/` (AddFieldSerializer). */
export interface FieldCreate {
  slug: string;
  name: string;
  field_type: string;
  description?: string;
  is_promoted?: boolean;
  is_filterable?: boolean;
  is_sortable?: boolean;
  is_searchable?: boolean;
  has_index?: boolean;
  is_required?: boolean;
  is_unique?: boolean;
  default_value?: unknown;
  config?: Record<string, unknown>;
  order?: number;
  read_roles?: string[];
  write_roles?: string[];
}

/** Body for `PATCH /metadata/entities/{slug}/fields/{field_slug}/` — all optional. */
export type FieldUpdate = Partial<FieldCreate> & {
  is_hidden?: boolean;
  is_readonly?: boolean;
};

/** Full FieldDefinition as returned by the fields endpoints (FieldDefinitionOutputSerializer). */
export interface FieldDef {
  id: string;
  slug: string;
  name: string;
  field_type: string;
  description: string;
  is_promoted: boolean;
  column_name: string;
  is_filterable: boolean;
  is_sortable: boolean;
  is_searchable: boolean;
  has_index: boolean;
  is_required: boolean;
  is_unique: boolean;
  default_value: unknown;
  is_system: boolean;
  is_hidden: boolean;
  is_readonly: boolean;
  order: number;
  config: Record<string, unknown>;
  read_roles: string[];
  write_roles: string[];
  created_at?: string;
  updated_at?: string;
}

/** Module create/update body. */
export interface ModuleWrite {
  name: string;
  slug?: string;
  description?: string;
  icon?: string;
  color?: string;
  order?: number;
}

/** A saved Form Builder layout (FormDefinitionOutputSerializer). */
export interface FormDefinition {
  id: string;
  entity: string;
  entity_slug: string;
  name: string;
  is_default: boolean;
  is_public: boolean;
  layout: FormSection[];
  settings: Record<string, unknown>;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

/** Body for `POST /entities/{slug}/forms/` (FormCreateSerializer). */
export interface FormCreate {
  name: string;
  is_default?: boolean;
  is_public?: boolean;
  layout?: FormSection[];
  settings?: Record<string, unknown>;
}

export type FormUpdate = Partial<FormCreate>;

/** One entry from `GET /entities/{slug}/schema-versions/`. */
export interface SchemaVersion {
  id: string;
  version: number;
  snapshot: Record<string, unknown>;
  migration_sql: string;
  applied_at: string | null;
  applied_by: string | null;
  is_current: boolean;
  parent_version: number | null;
}
