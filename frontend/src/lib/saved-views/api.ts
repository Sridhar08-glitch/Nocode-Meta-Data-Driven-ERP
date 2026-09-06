/**
 * Saved Views client (Phase F1.9) — per-member view personalization against
 * `/api/v1/saved-views/`. A SavedView is a member's overlay (hidden fields, column widths,
 * personal NQL filters, sort overrides, group-by, pin) on a canonical ViewDefinition.
 * List is `{results, count}`; create requires `entity_slug`.
 */
import { apiGet, apiSend } from "@/lib/api/request";

import type { SortClause } from "@/lib/nql/types";

export interface SavedView {
  id: string;
  entity_id: string;
  name: string;
  hidden_field_slugs: string[];
  column_widths: Record<string, number>;
  personal_filters: unknown[];
  sort_overrides: SortClause[];
  group_by_override: string;
  is_pinned: boolean;
}

export interface SavedViewCreate {
  entity_slug: string;
  view_definition_id?: string;
  name?: string;
  hidden_field_slugs?: string[];
  column_widths?: Record<string, number>;
  personal_filters?: unknown[];
  sort_overrides?: SortClause[];
  group_by_override?: string;
  is_pinned?: boolean;
}

/** Only these fields are mutable via PATCH (entity/definition/member are immutable). */
export type SavedViewUpdate = Partial<Omit<SavedViewCreate, "entity_slug" | "view_definition_id">>;

export interface SavedViewList {
  results: SavedView[];
  count: number;
}

export const savedViewsApi = {
  list: (entitySlug?: string) =>
    apiGet<SavedViewList>(
      `/api/v1/saved-views/${entitySlug ? `?entity_slug=${encodeURIComponent(entitySlug)}` : ""}`,
    ),
  get: (id: string) => apiGet<SavedView>(`/api/v1/saved-views/${id}/`),
  create: (data: SavedViewCreate) => apiSend<SavedView>("/api/v1/saved-views/", "POST", data),
  update: (id: string, data: SavedViewUpdate) =>
    apiSend<SavedView>(`/api/v1/saved-views/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<null>(`/api/v1/saved-views/${id}/`, "DELETE"),
};
