/**
 * Public-forms ADMIN client (Phase P1.5) — authenticated form management + submission review over
 * `/api/v1/public-forms/` (backend Phase 1.24). Distinct from the unauthenticated runtime client in
 * `api.ts`. Form *creation/layout* lives in the Studio form builder; here we publish/unpublish and
 * triage submissions.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface PublicFormDef {
  id: string;
  entity: string;
  entity_slug: string;
  name: string;
  is_default: boolean;
  is_public: boolean;
  created_at: string;
}
export interface FormSubmission {
  id: string;
  form_id: string;
  entity_id: string;
  status: string;
  data: Record<string, unknown>;
  created_record_id: string | null;
  submitter_name: string;
  submitter_email: string;
  honeypot_triggered: boolean;
  spam_score: number;
  validation_errors: unknown[];
  rejection_reason: string;
  created_at: string;
}

const P = "/api/v1/public-forms";

export const publicFormsAdminApi = {
  listForms: () => apiGet<{ results: PublicFormDef[] }>(`${P}/forms/`),
  updateForm: (id: string, data: { is_public?: boolean; name?: string }) =>
    apiSend<PublicFormDef>(`${P}/forms/${id}/`, "PATCH", data),
  listSubmissions: (formId: string, status?: string) =>
    apiGet<{ results: FormSubmission[]; count: number }>(`${P}/forms/${formId}/submissions/${status ? `?status=${status}` : ""}`),
  approve: (formId: string, subId: string) =>
    apiSend<FormSubmission>(`${P}/forms/${formId}/submissions/${subId}/approve/`, "POST"),
  reject: (formId: string, subId: string, reason: string) =>
    apiSend<FormSubmission>(`${P}/forms/${formId}/submissions/${subId}/reject/`, "POST", { reason }),
};
