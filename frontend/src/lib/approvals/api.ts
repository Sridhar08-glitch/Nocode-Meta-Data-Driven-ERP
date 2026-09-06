/**
 * Approvals client (Phase F2.4) — ApprovalProcess config (the matrix) + the request lifecycle over
 * `/api/v1/approvals/`. Requests are spawned server-side (by workflows), so the API only
 * lists/reads/resolves them. Entity binding is by `entity_id`.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type ApproverType = "role" | "member" | "field";
export type Quorum = "any" | "all";
export type OnTimeout = "escalate" | "auto_reject" | "auto_approve";

export interface ApproverSpec {
  type: ApproverType;
  value: string;
}
export interface ApprovalLevel {
  level: number;
  approvers: ApproverSpec[];
  quorum: Quorum;
  timeout_hours?: number;
  on_timeout?: OnTimeout;
}
export interface ProcessAction {
  type: string;
  [k: string]: unknown;
}

export interface ApprovalProcess {
  id: string;
  name: string;
  slug: string;
  entity_id: string | null;
  trigger_condition_nql: string;
  levels: ApprovalLevel[];
  on_approve_actions: ProcessAction[];
  on_reject_actions: ProcessAction[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface ApprovalProcessWrite {
  name: string;
  slug: string;
  entity_id?: string | null;
  trigger_condition_nql?: string;
  levels?: ApprovalLevel[];
  on_approve_actions?: ProcessAction[];
  on_reject_actions?: ProcessAction[];
  is_active?: boolean;
}

export type ApprovalStatus = "pending" | "approved" | "rejected" | "cancelled" | "expired";
export interface ApprovalDecision {
  id: string;
  level: number;
  approver_id: string;
  decision: "approve" | "reject";
  comment: string;
  decided_at: string;
}
export interface ApprovalRequest {
  id: string;
  process_id: string;
  entity_id: string | null;
  record_id: string | null;
  status: ApprovalStatus;
  current_level: number;
  requested_by: string;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_comment: string;
  expires_at: string | null;
  created_at: string;
  decisions: ApprovalDecision[];
}
export interface Paged<T> {
  results: T[];
  count: number;
}

export const APPROVER_TYPE_OPTIONS: { value: ApproverType; label: string }[] = [
  { value: "role", label: "Role" },
  { value: "member", label: "Member" },
  { value: "field", label: "Field on record" },
];
export const QUORUM_OPTIONS: { value: Quorum; label: string }[] = [
  { value: "any", label: "Any approver" },
  { value: "all", label: "All approvers" },
];
export const ON_TIMEOUT_OPTIONS: { value: OnTimeout; label: string }[] = [
  { value: "auto_reject", label: "Auto-reject" },
  { value: "auto_approve", label: "Auto-approve" },
  { value: "escalate", label: "Escalate" },
];

const A = "/api/v1/approvals";

export const approvalsApi = {
  listProcesses: () => apiGet<Paged<ApprovalProcess>>(`${A}/processes/`),
  getProcess: (id: string) => apiGet<ApprovalProcess>(`${A}/processes/${id}/`),
  createProcess: (data: ApprovalProcessWrite) => apiSend<ApprovalProcess>(`${A}/processes/`, "POST", data),
  updateProcess: (id: string, data: Partial<ApprovalProcessWrite>) =>
    apiSend<ApprovalProcess>(`${A}/processes/${id}/`, "PATCH", data),
  deleteProcess: (id: string) => apiSend<null>(`${A}/processes/${id}/`, "DELETE"),

  listRequests: (params: { status?: string; pending_for_me?: boolean } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.pending_for_me) qs.set("pending_for_me", "1");
    const s = qs.toString();
    return apiGet<Paged<ApprovalRequest>>(`${A}/requests/${s ? `?${s}` : ""}`);
  },
  pendingForMe: () => apiGet<Paged<ApprovalRequest>>(`${A}/requests/pending-for-me/`),
  approve: (id: string, comment = "") => apiSend<ApprovalRequest>(`${A}/requests/${id}/approve/`, "POST", { comment }),
  reject: (id: string, comment = "") => apiSend<ApprovalRequest>(`${A}/requests/${id}/reject/`, "POST", { comment }),
  cancel: (id: string) => apiSend<ApprovalRequest>(`${A}/requests/${id}/cancel/`, "POST"),
};
