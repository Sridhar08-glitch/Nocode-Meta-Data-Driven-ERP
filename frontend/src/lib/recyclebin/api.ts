/**
 * Recycle Bin client (Phase F3.4) — list + restore + purge over `/api/v1/recyclebin/`
 * (backend Phase 1.22). Restore = member; purge = admin (hard delete). Entries auto-purge after
 * `purge_after`. Read endpoints never expose storage details.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface RecycleBinEntry {
  id: string;
  entity_id: string | null;
  entity_slug: string;
  record_id: string;
  record_title: string;
  deleted_by: string | null;
  deleted_at: string;
  purge_after: string;
  cascade_entries: { entity_slug: string; record_id: string }[];
  is_purged: boolean;
  purged_at: string | null;
  created_at: string;
}

export interface RecycleBinList {
  results: RecycleBinEntry[];
}

export interface RecycleBinFilters {
  entity_slug?: string;
  include_purged?: boolean;
}

function query(f: RecycleBinFilters): string {
  const qs = new URLSearchParams();
  if (f.entity_slug) qs.set("entity_slug", f.entity_slug);
  if (f.include_purged) qs.set("include_purged", "1");
  const s = qs.toString();
  return s ? `?${s}` : "";
}

const R = "/api/v1/recyclebin";

export const recycleBinApi = {
  list: (filters: RecycleBinFilters = {}) => apiGet<RecycleBinList>(`${R}/${query(filters)}`),
  restore: (id: string) => apiSend<{ restored: boolean }>(`${R}/${id}/restore/`, "POST"),
  purge: (id: string) => apiSend<{ purged: boolean }>(`${R}/${id}/purge/`, "POST"),
  bulkRestore: (entryIds: string[]) => apiSend<{ restored: number }>(`${R}/bulk-restore/`, "POST", { entry_ids: entryIds }),
  bulkPurge: (entryIds: string[]) => apiSend<{ purged: number }>(`${R}/bulk-purge/`, "POST", { entry_ids: entryIds }),
};
