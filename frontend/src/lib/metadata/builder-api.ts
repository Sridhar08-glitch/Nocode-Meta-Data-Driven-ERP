/**
 * Metadata write API (Phase F1.8 builders) — entity / field / module / form CRUD,
 * field promote/demote, and schema-version rollback. Read endpoints stay in `api.ts`.
 * Entities + fields are addressed BY SLUG; modules + forms by UUID (backend contract).
 */
import { apiGet, apiSend } from "@/lib/api/request";

/** A config object that references the entity/field being deleted. */
export interface ImpactDependent {
  type: string;
  name: string;
  detail: string;
  approximate: boolean;
  id: string | null;
}
export interface ImpactResult {
  dependents: ImpactDependent[];
  count: number;
}

import type {
  EntityCreate,
  EntityMeta,
  EntityUpdate,
  FieldCreate,
  FieldDef,
  FieldUpdate,
  FormCreate,
  FormDefinition,
  FormUpdate,
  ModuleMeta,
  ModuleWrite,
  SchemaVersion,
} from "./types";

export const builderApi = {
  // entities
  createEntity: (data: EntityCreate) =>
    apiSend<EntityMeta>("/api/v1/metadata/entities/", "POST", data),
  updateEntity: (slug: string, data: EntityUpdate) =>
    apiSend<EntityMeta>(`/api/v1/metadata/entities/${slug}/`, "PATCH", data),
  deleteEntity: (slug: string) =>
    apiSend<null>(`/api/v1/metadata/entities/${slug}/`, "DELETE"),

  // fields
  listFields: (slug: string) =>
    apiGet<FieldDef[]>(`/api/v1/metadata/entities/${slug}/fields/`),
  createField: (slug: string, data: FieldCreate) =>
    apiSend<FieldDef>(`/api/v1/metadata/entities/${slug}/fields/`, "POST", data),
  updateField: (slug: string, fieldSlug: string, data: FieldUpdate) =>
    apiSend<FieldDef>(`/api/v1/metadata/entities/${slug}/fields/${fieldSlug}/`, "PATCH", data),
  deleteField: (slug: string, fieldSlug: string) =>
    apiSend<null>(`/api/v1/metadata/entities/${slug}/fields/${fieldSlug}/`, "DELETE"),

  // impact analysis (what config references this entity/field) — shown before delete
  entityImpact: (slug: string) =>
    apiGet<ImpactResult>(`/api/v1/metadata/entities/${slug}/impact/`),
  fieldImpact: (slug: string, fieldSlug: string) =>
    apiGet<ImpactResult>(`/api/v1/metadata/entities/${slug}/fields/${fieldSlug}/impact/`),
  promoteField: (slug: string, fieldSlug: string) =>
    apiSend<FieldDef>(`/api/v1/metadata/entities/${slug}/promote-field/`, "POST", {
      field_slug: fieldSlug,
    }),
  demoteField: (slug: string, fieldSlug: string) =>
    apiSend<FieldDef>(`/api/v1/metadata/entities/${slug}/demote-field/`, "POST", {
      field_slug: fieldSlug,
    }),

  // schema versions
  schemaVersions: (slug: string) =>
    apiGet<SchemaVersion[]>(`/api/v1/metadata/entities/${slug}/schema-versions/`),
  rollbackSchema: (slug: string, version: number) =>
    apiSend<EntityMeta>(
      `/api/v1/metadata/entities/${slug}/schema-versions/${version}/rollback/`,
      "POST",
    ),

  // modules
  createModule: (data: ModuleWrite) =>
    apiSend<ModuleMeta>("/api/v1/metadata/modules/", "POST", data),
  updateModule: (id: string, data: Partial<ModuleWrite>) =>
    apiSend<ModuleMeta>(`/api/v1/metadata/modules/${id}/`, "PATCH", data),
  deleteModule: (id: string) => apiSend<null>(`/api/v1/metadata/modules/${id}/`, "DELETE"),

  // forms (Form Builder)
  listForms: (slug: string) =>
    apiGet<FormDefinition[]>(`/api/v1/metadata/entities/${slug}/forms/`),
  getForm: (slug: string, formId: string) =>
    apiGet<FormDefinition>(`/api/v1/metadata/entities/${slug}/forms/${formId}/`),
  createForm: (slug: string, data: FormCreate) =>
    apiSend<FormDefinition>(`/api/v1/metadata/entities/${slug}/forms/`, "POST", data),
  updateForm: (slug: string, formId: string, data: FormUpdate) =>
    apiSend<FormDefinition>(
      `/api/v1/metadata/entities/${slug}/forms/${formId}/`,
      "PATCH",
      data,
    ),
  deleteForm: (slug: string, formId: string) =>
    apiSend<null>(`/api/v1/metadata/entities/${slug}/forms/${formId}/`, "DELETE"),
};
