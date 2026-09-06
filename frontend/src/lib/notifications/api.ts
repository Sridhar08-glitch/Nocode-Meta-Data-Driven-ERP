/** Notifications client (Phase F1.10) — recipient inbox over `/api/v1/notifications/`. */
import { apiGet, apiSend } from "@/lib/api/request";

export type NotificationChannel = "in_app" | "email" | "push" | "sms";
export type NotificationStatus = "pending" | "sent" | "delivered" | "failed" | "read";

export interface Notification {
  id: string;
  template_id: string | null;
  recipient_id: string;
  recipient_type: "member" | "portal_user";
  channel: NotificationChannel;
  status: NotificationStatus;
  subject: string;
  body: string;
  action_url: string;
  entity_id: string | null;
  record_id: string | null;
  group_key: string;
  actor_id: string | null;
  sent_at: string | null;
  /** null = unread. */
  read_at: string | null;
  failed_reason: string;
  created_at: string;
}

export interface NotificationList {
  results: Notification[];
  count: number;
}

export interface NotificationListParams {
  unread?: boolean;
  channel?: string;
  date_from?: string;
}

/** The reduced shape pushed over `ws/notifications/` (not the full REST object). */
export interface NotificationPush {
  id: string;
  subject: string;
  body: string;
  channel: NotificationChannel;
  action_url: string;
  group_key: string;
  created_at: string | null;
}

function listQuery(params: NotificationListParams): string {
  const qs = new URLSearchParams();
  if (params.unread) qs.set("unread", "1");
  if (params.channel) qs.set("channel", params.channel);
  if (params.date_from) qs.set("date_from", params.date_from);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export const notificationsApi = {
  list: (params: NotificationListParams = {}) =>
    apiGet<NotificationList>(`/api/v1/notifications/${listQuery(params)}`),
  markRead: (id: string) => apiSend<Notification>(`/api/v1/notifications/${id}/read/`, "POST"),
  markAllRead: () => apiSend<{ updated: number }>("/api/v1/notifications/read-all/", "POST"),
  unreadCount: () => apiGet<{ count: number }>("/api/v1/notifications/unread-count/"),
};

// ── notification templates (Phase F2.7) ──────────────────────────────────────────────
export type TemplateChannel = "in_app" | "email" | "push" | "sms" | "webhook";

export interface NotificationTemplate {
  id: string;
  slug: string;
  name: string;
  channel: TemplateChannel;
  subject_template: string;
  body_template: string;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}
export interface NotificationTemplateWrite {
  slug: string;
  name: string;
  channel: TemplateChannel;
  subject_template?: string;
  body_template?: string;
}

export const TEMPLATE_CHANNEL_OPTIONS: { value: TemplateChannel; label: string }[] = [
  { value: "in_app", label: "In-app" },
  { value: "email", label: "Email" },
  { value: "push", label: "Push" },
  { value: "sms", label: "SMS" },
  { value: "webhook", label: "Webhook" },
];

/** Extract `${var}` placeholders from a template body/subject (Python string.Template syntax). */
export function templateVariables(...parts: string[]): string[] {
  const found = new Set<string>();
  for (const p of parts) {
    for (const m of Array.from(p.matchAll(/\$\{(\w+)\}/g))) found.add(m[1]);
  }
  return Array.from(found);
}

/** Client-side preview of `${var}` substitution (the backend render is authoritative on test-send). */
export function renderPreview(template: string, context: Record<string, string>): string {
  return template.replace(/\$\{(\w+)\}/g, (_, k) => (k in context ? context[k] : `\${${k}}`));
}

// ── notification preferences (Phase F2.7) ────────────────────────────────────────────
export interface NotificationPreference {
  id: string;
  event_type: string;
  channel: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

/** Common notification event types offered in the preferences matrix. */
export const PREFERENCE_EVENT_TYPES: { value: string; label: string }[] = [
  { value: "record_assigned", label: "Assigned to me" },
  { value: "comment_mention", label: "Mentioned in a comment" },
  { value: "approval_requested", label: "Approval requested" },
  { value: "approval_approved", label: "Approval approved" },
  { value: "approval_rejected", label: "Approval rejected" },
  { value: "sla_warning", label: "SLA warning" },
  { value: "sla_breached", label: "SLA breached" },
  { value: "workflow_completed", label: "Workflow completed" },
];
export const PREFERENCE_CHANNELS: { value: string; label: string }[] = [
  { value: "in_app", label: "In-app" },
  { value: "email", label: "Email" },
];

export const preferencesApi = {
  list: () => apiGet<{ results: NotificationPreference[]; count: number }>("/api/v1/notifications/preferences/"),
  set: (event_type: string, channel: string, enabled: boolean) =>
    apiSend<NotificationPreference>("/api/v1/notifications/preferences/", "PUT", { event_type, channel, enabled }),
};

export const templatesApi = {
  list: () => apiGet<NotificationTemplate[] | { results: NotificationTemplate[]; count: number }>("/api/v1/notifications/templates/"),
  get: (id: string) => apiGet<NotificationTemplate>(`/api/v1/notifications/templates/${id}/`),
  create: (data: NotificationTemplateWrite) =>
    apiSend<NotificationTemplate>("/api/v1/notifications/templates/", "POST", data),
  update: (id: string, data: Partial<NotificationTemplateWrite>) =>
    apiSend<NotificationTemplate>(`/api/v1/notifications/templates/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<null>(`/api/v1/notifications/templates/${id}/`, "DELETE"),
  test: (id: string, context: Record<string, unknown> = {}) =>
    apiSend<{ sent: number; notifications: Notification[] }>(`/api/v1/notifications/templates/${id}/test/`, "POST", { context }),
};
