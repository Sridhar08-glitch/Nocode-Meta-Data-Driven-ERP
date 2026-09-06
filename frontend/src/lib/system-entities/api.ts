/**
 * System-Entity Adapter (B0.2) client — talks to /api/v1/system-entities/. Exposes a records API
 * with the SAME surface as `recordsApi` (list/get/create/update/remove) so the source-aware runtime
 * hooks can dispatch to it transparently. Translates the runtime's ListParams (limit/offset/sort/
 * filter) into the B0 records query (page/page_size/sort/<field>=<val>).
 */
import { apiGet, apiSend } from "@/lib/api/request";
import type { ListParams, RecordList } from "@/lib/records/api";

import type { SystemEntityDescriptor, SystemEntityListItem } from "./adapt";

function recordsQuery(params: ListParams): string {
  const qs = new URLSearchParams();
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;
  qs.set("page", String(Math.floor(offset / Math.max(1, limit)) + 1));
  qs.set("page_size", String(limit));
  if (params.sort?.length) {
    const s = params.sort[0];
    qs.set("sort", s.direction === "desc" ? `-${s.field}` : s.field);
  }
  // Only simple equality filters are supported by system entities; pass field:value pairs through.
  if (params.filter && typeof params.filter === "object") {
    for (const [k, v] of Object.entries(params.filter as Record<string, unknown>)) {
      if (v != null && v !== "") qs.set(k, String(v));
    }
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export const systemEntitiesApi = {
  list: () => apiGet<SystemEntityListItem[]>("/api/v1/system-entities/"),
  descriptor: (slug: string) =>
    apiGet<SystemEntityDescriptor>(`/api/v1/system-entities/${slug}/`),

  records: {
    list: (slug: string, params: ListParams = {}): Promise<RecordList> =>
      apiGet<{ results: Record<string, unknown>[]; count: number }>(
        `/api/v1/system-entities/${slug}/records/${recordsQuery(params)}`,
      ),
    get: (slug: string, id: string) =>
      apiGet<Record<string, unknown>>(`/api/v1/system-entities/${slug}/records/${id}/`),
    create: (slug: string, data: Record<string, unknown>) =>
      apiSend<Record<string, unknown>>(`/api/v1/system-entities/${slug}/records/`, "POST", data),
    update: (slug: string, id: string, data: Record<string, unknown>) =>
      apiSend<Record<string, unknown>>(
        `/api/v1/system-entities/${slug}/records/${id}/`,
        "PATCH",
        data,
      ),
    remove: (slug: string, id: string) =>
      apiSend<null>(`/api/v1/system-entities/${slug}/records/${id}/`, "DELETE"),
  },
};

export { recordsQuery };
