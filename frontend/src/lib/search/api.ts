/**
 * Search client (Phase F2.6) — full-text search over `/api/v1/search/` (powers Cmd+K + the global
 * search page) plus saved/recent searches. The main search returns `{results, total}` (not count).
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface SearchResult {
  entity_slug: string;
  record_id: string;
  title: string;
  snippet: string;
  rank: number;
}
export interface SearchResponse {
  results: SearchResult[];
  total: number;
}
export interface RecentSearch {
  id: string;
  query_text: string;
  entity_slug: string | null;
  result_count: number;
  searched_at: string;
}
export interface Paged<T> {
  results: T[];
  count: number;
}

export const searchApi = {
  search: (q: string, opts: { entity?: string; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams({ q });
    if (opts.entity) qs.set("entity", opts.entity);
    if (opts.limit) qs.set("limit", String(opts.limit));
    if (opts.offset) qs.set("offset", String(opts.offset));
    return apiGet<SearchResponse>(`/api/v1/search/?${qs.toString()}`);
  },
  recent: () => apiGet<Paged<RecentSearch>>("/api/v1/search/recent/"),
  clearRecent: () => apiSend<{ cleared: number }>("/api/v1/search/recent/", "DELETE"),
};
