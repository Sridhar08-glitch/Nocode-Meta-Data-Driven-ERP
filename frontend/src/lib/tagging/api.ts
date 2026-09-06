/**
 * Tagging client (Phase F2.5) — workspace tags + per-record attach/detach over `/api/v1/tags/`.
 * Attach/detach live under `/api/v1/tags/records/` (not under /data/). Filtering records by tag is
 * done through the records/NQL endpoint, not here.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface Tag {
  id: string;
  name: string;
  slug: string;
  color: string;
  group: string;
}
export interface TagCreate {
  name: string;
  slug: string;
  color?: string;
  group?: string;
}
export interface Paged<T> {
  results: T[];
  count: number;
}

const T = "/api/v1/tags";

export const tagsApi = {
  list: () => apiGet<Paged<Tag>>(`${T}/`),
  create: (data: TagCreate) => apiSend<Tag>(`${T}/`, "POST", data),
  forRecord: (recordId: string) => apiGet<Paged<Tag>>(`${T}/records/?record_id=${encodeURIComponent(recordId)}`),
  attach: (entitySlug: string, tagId: string, recordId: string) =>
    apiSend<{ detail: string }>(`${T}/records/`, "POST", { entity_slug: entitySlug, tag_id: tagId, record_id: recordId }),
  detach: (tagId: string, recordId: string) =>
    apiSend<{ removed: number }>(`${T}/records/`, "DELETE", { tag_id: tagId, record_id: recordId }),
};
