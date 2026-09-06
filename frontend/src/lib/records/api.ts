/**
 * Auto-CRUD record API (Phase F1.7) — one client for EVERY entity, resolved by slug.
 * No per-entity code: the metadata drives everything.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface RecordList {
  results: Record<string, unknown>[];
  count: number;
}

export interface ListParams {
  filter?: unknown;
  sort?: { field: string; direction: "asc" | "desc" }[];
  limit?: number;
  offset?: number;
}

function listQuery(params: ListParams): string {
  const qs = new URLSearchParams();
  if (params.filter) qs.set("filter", JSON.stringify(params.filter));
  if (params.sort?.length) {
    qs.set("sort", params.sort.map((s) => (s.direction === "desc" ? `-${s.field}` : s.field)).join(","));
  }
  if (params.limit != null) qs.set("limit", String(params.limit));
  if (params.offset != null) qs.set("offset", String(params.offset));
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export const recordsApi = {
  list: (slug: string, params: ListParams = {}) =>
    apiGet<RecordList>(`/api/v1/data/${slug}/${listQuery(params)}`),
  get: (slug: string, id: string) =>
    apiGet<Record<string, unknown>>(`/api/v1/data/${slug}/${id}/`),
  create: (slug: string, data: Record<string, unknown>) =>
    apiSend<Record<string, unknown>>(`/api/v1/data/${slug}/`, "POST", data),
  update: (slug: string, id: string, data: Record<string, unknown>) =>
    apiSend<Record<string, unknown>>(`/api/v1/data/${slug}/${id}/`, "PATCH", data),
  remove: (slug: string, id: string) => apiSend<null>(`/api/v1/data/${slug}/${id}/`, "DELETE"),
  restore: (slug: string, id: string) =>
    apiSend<Record<string, unknown>>(`/api/v1/data/${slug}/${id}/restore/`, "POST"),
  timeline: (slug: string, id: string) =>
    apiGet<{ results: unknown[] }>(`/api/v1/data/${slug}/${id}/timeline/`),
  activity: (slug: string, id: string) =>
    apiGet<{ results: unknown[] }>(`/api/v1/data/${slug}/${id}/activity/`),
  sla: (slug: string, id: string) => apiGet<unknown>(`/api/v1/data/${slug}/${id}/sla/`),
};

export { listQuery };
