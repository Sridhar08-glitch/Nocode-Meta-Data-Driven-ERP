/**
 * CRM Solution client (Phase P2.6) — the CRM pipeline lifecycle actions the generic metadata
 * runtime can't express, over `/api/v1/crm/` (backend live). The solution's leads/accounts/
 * contacts/opportunities/activities CRUD is rendered by the generic F1.7 record runtime at
 * `/e/<entity_slug>`; this client only drives setup + document numbering + qualify/win/lose/complete.
 */
import { apiGet, apiSend } from "@/lib/api/request";

/** CRM document entity slugs (provisioned by the CRM solution template). */
export type CrmEntitySlug = "lead" | "account" | "contact" | "opportunity" | "activity";

/** A created/updated CRM record. Numbered documents (lead/account/opportunity) carry a `number`. */
export interface CrmRecord {
  id: string;
  number?: string;
  status?: string;
  stage?: string;
  [field: string]: unknown;
}

/** Qualifying a lead also spins up a linked, numbered Opportunity. */
export interface QualifyLeadResult {
  lead: CrmRecord;
  opportunity: CrmRecord;
}

const C = "/api/v1/crm";

export const crmApi = {
  /** Ensure LEAD / ACC / OPP gapless number sequences exist (admin). */
  setup: () => apiSend<{ detail: string }>(`${C}/setup/`, "POST"),

  /** Create a CRM document; lead/account/opportunity get a gapless `number` auto-allocated. */
  createDocument: (entitySlug: CrmEntitySlug, data: Record<string, unknown>) =>
    apiSend<CrmRecord>(`${C}/${entitySlug}/`, "POST", data),

  /** Qualify a lead (status→qualified) and create a linked, numbered Opportunity. */
  qualifyLead: (recordId: string) =>
    apiSend<QualifyLeadResult>(`${C}/leads/${recordId}/qualify/`, "POST"),

  /** Mark an opportunity won (stage→won + close reason). */
  winOpportunity: (recordId: string, reason: string) =>
    apiSend<CrmRecord>(`${C}/opportunities/${recordId}/win/`, "POST", { reason }),

  /** Mark an opportunity lost (stage→lost + close reason). */
  loseOpportunity: (recordId: string, reason: string) =>
    apiSend<CrmRecord>(`${C}/opportunities/${recordId}/lose/`, "POST", { reason }),

  /** Mark an activity completed (status→completed). */
  completeActivity: (recordId: string) =>
    apiSend<CrmRecord>(`${C}/activities/${recordId}/complete/`, "POST"),
};

/** Re-export so callers can import the GET helper consistently if needed later. */
export { apiGet };
