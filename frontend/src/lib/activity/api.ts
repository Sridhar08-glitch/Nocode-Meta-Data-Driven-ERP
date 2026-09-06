/**
 * Activity client (Phase F2.5) — the cross-entity feed `/api/v1/activity/feed/` and the per-record
 * event timeline used for Record Playback (`/api/v1/data/{slug}/{id}/timeline/`).
 */
import { apiGet } from "@/lib/api/request";

export interface FieldDiff {
  field_slug: string;
  field_label: string;
  old: unknown;
  new: unknown;
}
export interface ActivityEntry {
  id: string;
  entity_id: string | null;
  record_id: string | null;
  activity_type: string;
  actor_id: string | null;
  actor_type: string;
  actor_name: string;
  summary: string;
  changes: FieldDiff[];
  event_sequence: number | null;
  occurred_at: string;
  is_pinned: boolean;
}
export interface ActivityFeedParams {
  entity_slug?: string;
  activity_type?: string;
  actor_id?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}
export interface Paged<T> {
  results: T[];
  count: number;
}

/** One step of the per-record event history (Record Playback). */
export interface TimelineEvent {
  event_type: string;
  version: number;
  occurred_at: string;
  actor_id: string | null;
  changed_fields: string[];
}
export interface Timeline {
  events: TimelineEvent[];
  count: number;
}

function feedQuery(p: ActivityFeedParams): string {
  const qs = new URLSearchParams();
  for (const k of ["entity_slug", "activity_type", "actor_id", "date_from", "date_to"] as const) {
    if (p[k]) qs.set(k, String(p[k]));
  }
  if (p.limit) qs.set("limit", String(p.limit));
  if (p.offset) qs.set("offset", String(p.offset));
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export const activityApi = {
  feed: (params: ActivityFeedParams = {}) => apiGet<Paged<ActivityEntry>>(`/api/v1/activity/feed/${feedQuery(params)}`),
  recordActivity: (slug: string, recordId: string) =>
    apiGet<Paged<ActivityEntry>>(`/api/v1/data/${slug}/${recordId}/activity/`),
  timeline: (slug: string, recordId: string) =>
    apiGet<Timeline>(`/api/v1/data/${slug}/${recordId}/timeline/`),
};
