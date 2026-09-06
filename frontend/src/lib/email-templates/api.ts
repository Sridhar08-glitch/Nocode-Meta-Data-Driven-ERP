/**
 * Email Template client (Phase F3.6) — locale-aware email templates over `/api/v1/templates/email/`
 * (backend Phase 1.33). Unlike F2.7's NotificationTemplate, these have a `locale` (slug+locale is the
 * unique key). Render + test-send happen server-side (HTML sanitized). Reads = member; writes = admin.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface EmailTemplate {
  id: string;
  name: string;
  slug: string;
  locale: string;
  subject_template: string;
  body_html: string;
  blocks: unknown[];
  variables: string[];
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface EmailTemplateWrite {
  name: string;
  slug: string;
  locale: string;
  subject_template?: string;
  body_html?: string;
}
export interface RenderedEmail {
  subject: string;
  html: string;
}

const E = "/api/v1/templates/email";

export const emailTemplatesApi = {
  list: () => apiGet<{ results: EmailTemplate[]; count: number }>(`${E}/`),
  get: (id: string) => apiGet<EmailTemplate>(`${E}/${id}/`),
  create: (data: EmailTemplateWrite) => apiSend<EmailTemplate>(`${E}/`, "POST", data),
  update: (id: string, data: Partial<EmailTemplateWrite>) => apiSend<EmailTemplate>(`${E}/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<null>(`${E}/${id}/`, "DELETE"),
  render: (id: string, context: Record<string, unknown> = {}) => apiSend<RenderedEmail>(`${E}/${id}/render/`, "POST", { context }),
  testSend: (id: string, toEmail: string, context: Record<string, unknown> = {}) =>
    apiSend<{ sent?: boolean }>(`${E}/${id}/test-send/`, "POST", { to_email: toEmail, context }),
};
