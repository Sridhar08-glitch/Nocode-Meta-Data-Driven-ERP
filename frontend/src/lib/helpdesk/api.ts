/**
 * Helpdesk + ITSM client (Phase P2.11) — over `/api/v1/helpdesk/` (backend live). HYBRID:
 * the helpdesk entities (ticket_category, ticket, ticket_task, ticket_comment, kb_article, problem,
 * itsm_change, major_incident, service_contract, ticket_csat, agent_profile, field_service_visit) are
 * framework metadata rendered by the generic F1.7 record runtime at `/e/<entity_slug>`; this client only
 * drives what the metadata runtime can't express:
 *   • ticket lifecycle (create TKT-numbered + SLA-attached, assign / auto-assign, escalate, set status,
 *     resolve, close, CSAT)
 *   • the ITSM change approval
 *   • the NATIVE knowledge-recommendation (deterministic keyword/category match — NO AI) and SLA
 *     dashboard read panels (the SLA dashboard reuses the SLA engine).
 */
import { apiGet, apiSend } from "@/lib/api/request";

const H = "/api/v1/helpdesk";

/** Helpdesk document entity slugs (framework metadata; rendered at `/e/<slug>`). */
export type HelpdeskEntitySlug =
  | "ticket_category"
  | "ticket"
  | "ticket_task"
  | "ticket_comment"
  | "kb_article"
  | "problem"
  | "itsm_change"
  | "major_incident"
  | "service_contract"
  | "ticket_csat"
  | "agent_profile"
  | "field_service_visit";

/** A created/updated helpdesk metadata record. Ticket gets a gapless number (TKT-) + an SLA attached. */
export interface HelpdeskRecord {
  id: string;
  number?: string;
  status?: string;
  [field: string]: unknown;
}

/** Auto-assignment strategy. */
export type AutoAssignMethod = "round_robin" | "load_based" | "skill_based" | "team_based";

/** A deterministic knowledge recommendation (keyword/category match — NO AI). */
export interface KnowledgeArticleHit {
  id: string;
  title: string;
  category: string;
  score: number;
  [field: string]: unknown;
}

/** Workspace SLA health (reuses the SLA engine). */
export interface SlaDashboard {
  breached: number;
  warning: number;
  on_track: number;
  met: number;
  paused: number;
  [field: string]: unknown;
}

export const helpdeskApi = {
  /** Ensure the TKT- gapless number sequence exists (admin). */
  setup: () => apiSend<{ detail: string }>(`${H}/setup/`, "POST"),

  /** Create a helpdesk document; ticket gets a gapless `number` + SLA. Body = field-slug dict. */
  createDocument: (entitySlug: HelpdeskEntitySlug, data: Record<string, unknown>) =>
    apiSend<HelpdeskRecord>(`${H}/${entitySlug}/`, "POST", data),

  // ── ticket lifecycle (by record id) ───────────────────────────────────────────
  /** Assign a ticket to an agent and/or team → status assigned. */
  assignTicket: (recordId: string, body: { agent?: string; team?: string }) =>
    apiSend<HelpdeskRecord>(`${H}/tickets/${recordId}/assign/`, "POST", body),

  /** Auto-pick an agent for a ticket (400 if none available). */
  autoAssignTicket: (recordId: string, body: { method: AutoAssignMethod; team?: string; skill?: string }) =>
    apiSend<HelpdeskRecord>(`${H}/tickets/${recordId}/auto-assign/`, "POST", body),

  /** Bump the ticket's escalation level. */
  escalateTicket: (recordId: string) => apiSend<HelpdeskRecord>(`${H}/tickets/${recordId}/escalate/`, "POST"),

  /** Change the ticket status (pauses/resumes SLA on waiting states). */
  setTicketStatus: (recordId: string, status: string) =>
    apiSend<HelpdeskRecord>(`${H}/tickets/${recordId}/status/`, "POST", { status }),

  /** Resolve a ticket → status resolved + marks SLA met. */
  resolveTicket: (recordId: string) => apiSend<HelpdeskRecord>(`${H}/tickets/${recordId}/resolve/`, "POST"),

  /** Close a ticket. */
  closeTicket: (recordId: string) => apiSend<HelpdeskRecord>(`${H}/tickets/${recordId}/close/`, "POST"),

  /** Submit a CSAT response for a ticket. */
  submitCsat: (recordId: string, body: { rating: number; feedback?: string; comments?: string }) =>
    apiSend<HelpdeskRecord>(`${H}/tickets/${recordId}/csat/`, "POST", body),

  // ── ITSM change approval ──────────────────────────────────────────────────────
  /** Approve an ITSM change → status approved (admin). */
  approveChange: (recordId: string) => apiSend<HelpdeskRecord>(`${H}/changes/${recordId}/approve/`, "POST"),

  // ── native knowledge recommendation (deterministic — NO AI) ───────────────────
  recommendKnowledge: (params: { category?: string; q?: string }) => {
    const qs = new URLSearchParams();
    if (params.category) qs.set("category", params.category);
    if (params.q) qs.set("q", params.q);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiGet<KnowledgeArticleHit[]>(`${H}/knowledge/recommend/${suffix}`);
  },

  // ── native SLA dashboard (reuses the SLA engine) ──────────────────────────────
  slaDashboard: () => apiGet<SlaDashboard>(`${H}/sla/dashboard/`),
};

export { apiGet };
