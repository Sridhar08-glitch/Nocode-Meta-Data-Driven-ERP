/** Relationship Builder API (Phase F1.8) — CRUD over `/api/v1/relationships/`. */
import { apiGet, apiSend } from "@/lib/api/request";

export type Cardinality = "one_to_one" | "one_to_many" | "many_to_many" | "self_ref";
export type OnDelete = "protect" | "cascade" | "set_null" | "detach";

export const CARDINALITY_OPTIONS: { value: Cardinality; label: string }[] = [
  { value: "one_to_one", label: "One to one (1:1)" },
  { value: "one_to_many", label: "One to many (1:N)" },
  { value: "many_to_many", label: "Many to many (N:N)" },
  { value: "self_ref", label: "Self reference" },
];

export const ON_DELETE_OPTIONS: { value: OnDelete; label: string }[] = [
  { value: "detach", label: "Detach (unlink)" },
  { value: "protect", label: "Protect (block delete)" },
  { value: "cascade", label: "Cascade (delete linked)" },
  { value: "set_null", label: "Set null" },
];

export interface RelationshipDef {
  id: string;
  name: string;
  slug: string;
  source_entity_id: string;
  target_entity_id: string;
  cardinality: Cardinality;
  on_delete: OnDelete;
  source_field_slug: string | null;
  target_field_slug: string | null;
  junction_table: string | null;
  is_system: boolean;
  created_at?: string;
}

export interface RelationshipCreate {
  name: string;
  slug: string;
  source_entity_id: string;
  target_entity_id: string;
  cardinality: Cardinality;
  on_delete?: OnDelete;
  source_field_slug?: string;
}

export const relationshipsApi = {
  list: (entityId?: string) =>
    apiGet<RelationshipDef[]>(
      `/api/v1/relationships/${entityId ? `?entity_id=${entityId}` : ""}`,
    ),
  get: (id: string) => apiGet<RelationshipDef>(`/api/v1/relationships/${id}/`),
  create: (data: RelationshipCreate) =>
    apiSend<RelationshipDef>("/api/v1/relationships/", "POST", data),
  remove: (id: string) => apiSend<null>(`/api/v1/relationships/${id}/`, "DELETE"),
};
