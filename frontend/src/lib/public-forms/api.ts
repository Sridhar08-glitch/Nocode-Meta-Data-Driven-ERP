/**
 * Public Forms client (Phase F3.8) — UNAUTHENTICATED. Fetches a public form's renderable schema and
 * submits to `/api/v1/public-forms/{id}/{schema,submit}/` with plain `fetch` (never the member
 * `authFetch`). The submit always returns `{success:true}` server-side (anti-enumeration); the
 * honeypot field is included to trap bots.
 */
import { API_BASE_URL } from "@/lib/api/config";
import { toApiError } from "@/lib/api/errors";
import type { FormSchema } from "@/lib/metadata/types";

export interface PublicFormSchema {
  form_id: string;
  name: string;
  entity_slug: string;
  honeypot_field: string;
  settings: Record<string, unknown>;
  schema: FormSchema;
}

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) throw toApiError(res, body);
  return body as T;
}

export const publicFormsApi = {
  schema: (formId: string) => fetch(`${API_BASE_URL}/api/v1/public-forms/${formId}/schema/`).then((r) => parse<PublicFormSchema>(r)),
  submit: (formId: string, data: Record<string, unknown>) =>
    fetch(`${API_BASE_URL}/api/v1/public-forms/${formId}/submit/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => parse<{ success: boolean }>(r)),
};
