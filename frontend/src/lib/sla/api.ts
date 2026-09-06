/**
 * SLA client (Phase F2.4) — policies + business-hours + dashboard over `/api/v1/sla/`, and the
 * per-record SLA status/pause/resume under `/api/v1/data/{slug}/{id}/sla/`. Entity binding by
 * `entity_id`. Business-hours has no DELETE route.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface SLATarget {
  metric: string;
  target_minutes: number;
  warning_at_percent?: number;
  business_hours_only?: boolean;
  business_hours_id?: string;
}
export interface SLAEscalationAction {
  type: "notify";
  recipient_id: string;
}
export interface SLAPolicy {
  id: string;
  name: string;
  slug: string;
  entity_id: string | null;
  description: string;
  applies_when_nql: string;
  targets: SLATarget[];
  escalation_actions: SLAEscalationAction[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface SLAPolicyWrite {
  name: string;
  slug: string;
  entity_id?: string | null;
  description?: string;
  applies_when_nql?: string;
  targets?: SLATarget[];
  escalation_actions?: SLAEscalationAction[];
  is_active?: boolean;
}

export interface Interval {
  start: string;
  end: string;
}
export interface Holiday {
  date: string;
  name?: string;
}
export interface BusinessHours {
  id: string;
  name: string;
  timezone: string;
  schedule: Record<string, Interval | null>;
  weekly_hours: Record<string, Interval[]>;
  shifts: Record<string, Interval[]>;
  holidays: Holiday[];
  region: string;
  created_at: string;
  updated_at: string;
}
export interface BusinessHoursWrite {
  name: string;
  timezone?: string;
  weekly_hours?: Record<string, Interval[]>;
  holidays?: Holiday[];
  region?: string;
  schedule?: Record<string, Interval | null>;
  shifts?: Record<string, Interval[]>;
}

export type SLAStatus = "on_track" | "warning" | "breached" | "met" | "paused";
export interface SLARecord {
  id: string;
  policy_id: string;
  entity_id: string;
  record_id: string;
  metric_key: string;
  status: SLAStatus;
  started_at: string;
  target_at: string;
  warning_at: string;
  paused_at: string | null;
  met_at: string | null;
  breached_at: string | null;
  paused_seconds: number;
  warning_sent: boolean;
  breach_notified: boolean;
}
export interface SLADashboard {
  breached: number;
  warning: number;
  on_track: number;
  met: number;
  paused: number;
}
export interface Paged<T> {
  results: T[];
  count: number;
}

export const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

const S = "/api/v1/sla";

export const slaApi = {
  listPolicies: () => apiGet<Paged<SLAPolicy>>(`${S}/policies/`),
  getPolicy: (id: string) => apiGet<SLAPolicy>(`${S}/policies/${id}/`),
  createPolicy: (data: SLAPolicyWrite) => apiSend<SLAPolicy>(`${S}/policies/`, "POST", data),
  updatePolicy: (id: string, data: Partial<SLAPolicyWrite>) => apiSend<SLAPolicy>(`${S}/policies/${id}/`, "PATCH", data),
  deletePolicy: (id: string) => apiSend<null>(`${S}/policies/${id}/`, "DELETE"),

  listBusinessHours: () => apiGet<Paged<BusinessHours>>(`${S}/business-hours/`),
  createBusinessHours: (data: BusinessHoursWrite) => apiSend<BusinessHours>(`${S}/business-hours/`, "POST", data),
  updateBusinessHours: (id: string, data: Partial<BusinessHoursWrite>) =>
    apiSend<BusinessHours>(`${S}/business-hours/${id}/`, "PATCH", data),

  dashboard: () => apiGet<SLADashboard>(`${S}/dashboard/`),

  recordStatus: (slug: string, recordId: string) =>
    apiGet<Paged<SLARecord>>(`/api/v1/data/${slug}/${recordId}/sla/`),
  pause: (slug: string, recordId: string) =>
    apiSend<{ paused: number; results: SLARecord[] }>(`/api/v1/data/${slug}/${recordId}/sla/pause/`, "POST"),
  resume: (slug: string, recordId: string) =>
    apiSend<{ resumed: number; results: SLARecord[] }>(`/api/v1/data/${slug}/${recordId}/sla/resume/`, "POST"),
};
