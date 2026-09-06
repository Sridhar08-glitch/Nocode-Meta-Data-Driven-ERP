/**
 * HR Solution client (Phase P2.7) — the HR lifecycle actions the generic metadata runtime can't
 * express, over `/api/v1/hr/` (backend live). The solution's org/recruitment/people/time/performance/
 * lifecycle entity CRUD is rendered by the generic F1.7 record runtime at `/e/<entity_slug>`; this
 * client only drives setup + document numbering + hire/complete/accept/approve/reject/promote/transfer/offboard.
 */
import { apiGet, apiSend } from "@/lib/api/request";

/** HR document entity slugs (provisioned by the HR solution template). */
export type HrEntitySlug =
  | "branch"
  | "division"
  | "department"
  | "team"
  | "position"
  | "job_family"
  | "job_grade"
  | "candidate"
  | "interview"
  | "offer"
  | "employee"
  | "onboarding_plan"
  | "onboarding_task"
  | "shift"
  | "attendance_record"
  | "leave_type"
  | "leave_balance"
  | "leave_request"
  | "holiday_calendar"
  | "review_cycle"
  | "goal"
  | "kpi"
  | "performance_review"
  | "promotion"
  | "transfer"
  | "exit_request"
  | "asset_return"
  | "clearance";

/** A created/updated HR record. Numbered documents (candidate/interview/offer/employee) carry a `number`. */
export interface HrRecord {
  id: string;
  number?: string;
  status?: string;
  [field: string]: unknown;
}

/** Hiring a candidate also creates a linked, EMP-numbered Employee. */
export interface HireCandidateResult {
  candidate: HrRecord;
  employee: HrRecord;
}

const H = "/api/v1/hr";

export const hrApi = {
  /** Ensure CAN / INT / OFF / EMP gapless number sequences exist (admin). */
  setup: () => apiSend<{ detail: string }>(`${H}/setup/`, "POST"),

  /** Create an HR document; candidate/interview/offer/employee get a gapless `number` auto-allocated. */
  createDocument: (entitySlug: HrEntitySlug, data: Record<string, unknown>) =>
    apiSend<HrRecord>(`${H}/${entitySlug}/`, "POST", data),

  /** Mark a candidate hired and create a linked, EMP-numbered Employee. */
  hireCandidate: (recordId: string) =>
    apiSend<HireCandidateResult>(`${H}/candidates/${recordId}/hire/`, "POST"),

  /** Mark an interview completed (status→completed). */
  completeInterview: (recordId: string) =>
    apiSend<HrRecord>(`${H}/interviews/${recordId}/complete/`, "POST"),

  /** Mark an offer accepted (status→accepted). */
  acceptOffer: (recordId: string) =>
    apiSend<HrRecord>(`${H}/offers/${recordId}/accept/`, "POST"),

  /** Approve a leave request (status→approved + decrements the linked leave balance). */
  approveLeave: (recordId: string) =>
    apiSend<HrRecord>(`${H}/leave-requests/${recordId}/approve/`, "POST"),

  /** Reject a leave request (status→rejected). */
  rejectLeave: (recordId: string) =>
    apiSend<HrRecord>(`${H}/leave-requests/${recordId}/reject/`, "POST"),

  /** Mark a performance review completed (status→completed). */
  completePerformance: (recordId: string) =>
    apiSend<HrRecord>(`${H}/performance-reviews/${recordId}/complete/`, "POST"),

  /** Promote an employee to a new position (a position record id/uuid). */
  promoteEmployee: (recordId: string, newPosition: string) =>
    apiSend<HrRecord>(`${H}/employees/${recordId}/promote/`, "POST", { new_position: newPosition }),

  /** Transfer an employee to a new department (a department record id/uuid). */
  transferEmployee: (recordId: string, newDepartment: string) =>
    apiSend<HrRecord>(`${H}/employees/${recordId}/transfer/`, "POST", { new_department: newDepartment }),

  /** Offboard an employee (status→terminated). */
  offboardEmployee: (recordId: string) =>
    apiSend<HrRecord>(`${H}/employees/${recordId}/offboard/`, "POST"),
};

/** Re-export so callers can import the GET helper consistently if needed later. */
export { apiGet };
