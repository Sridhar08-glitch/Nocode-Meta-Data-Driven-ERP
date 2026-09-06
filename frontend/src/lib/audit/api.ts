/**
 * Audit client (Phase F3.2) — the immutable audit log over `/api/v1/audit/` (backend Phase 1.10).
 * Owner/admin only; it's a read-only projection of the event store (no writes). Filterable by
 * resource_type / resource_id / action / actor_id, paginated via limit+offset.
 */
import { apiGet } from "@/lib/api/request";

export interface AuditEntry {
  id: string;
  actor_id: string | null;
  actor_type: string;
  actor_name: string;
  action: string;
  resource_type: string;
  resource_id: string;
  changed_fields: string[];
  correlation_id: string;
  event_id: string | null;
  occurred_at: string;
}

export interface AuditList {
  results: AuditEntry[];
  count: number;
}

export interface AuditFilters {
  resource_type?: string;
  resource_id?: string;
  action?: string;
  actor_id?: string;
  limit?: number;
  offset?: number;
}

function query(f: AuditFilters): string {
  const qs = new URLSearchParams();
  if (f.resource_type) qs.set("resource_type", f.resource_type);
  if (f.resource_id) qs.set("resource_id", f.resource_id);
  if (f.action) qs.set("action", f.action);
  if (f.actor_id) qs.set("actor_id", f.actor_id);
  qs.set("limit", String(f.limit ?? 50));
  qs.set("offset", String(f.offset ?? 0));
  return `?${qs.toString()}`;
}

export const auditApi = {
  list: (filters: AuditFilters = {}) => apiGet<AuditList>(`/api/v1/audit/${query(filters)}`),
};
