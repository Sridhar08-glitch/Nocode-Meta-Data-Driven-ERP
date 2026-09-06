/**
 * Project Management + PSA client (Phase P2.10) — over `/api/v1/projects/` (backend live). HYBRID:
 * the project entities (portfolio, program, project, task, milestone, deliverable, sprint, timesheet,
 * expense, risk, issue, change_request, quality_review, …) are framework metadata rendered by the
 * generic F1.7 record runtime at `/e/<entity_slug>`; this client only drives what the metadata
 * runtime can't express:
 *   • project / document lifecycle (create PRJ-/TSK-numbered, start/complete/baseline, budget approve,
 *     complete task/milestone, approve timesheet/expense/change-request/deliverable)
 *   • the NATIVE cost-rollup engine (cost entries + rollup onto the project)
 *   • the NATIVE financials/EVM, scheduling/critical-path, and resource/capacity read panels.
 */
import { apiGet, apiSend } from "@/lib/api/request";

const P = "/api/v1/projects";

/** Project document entity slugs (framework metadata; rendered at `/e/<slug>`). */
export type ProjectEntitySlug =
  | "portfolio"
  | "program"
  | "project"
  | "project_member"
  | "employee_skill"
  | "task"
  | "milestone"
  | "deliverable"
  | "task_dependency"
  | "sprint"
  | "timesheet"
  | "expense"
  | "risk"
  | "issue"
  | "change_request"
  | "quality_review";

/** A created/updated project metadata record. Project & task get gapless numbers (PRJ-/TSK-). */
export interface ProjectRecord {
  id: string;
  number?: string;
  status?: string;
  [field: string]: unknown;
}

export type CostSource = "payroll" | "procurement" | "asset" | "expense" | "timesheet" | "other";

export interface CostEntry {
  id: string;
  project_record_id: string;
  source: CostSource;
  amount: string;
  description: string;
  entry_date: string;
  [field: string]: unknown;
}

/** Result of rolling cost entries onto a project. */
export interface RollupResult {
  total_cost: string;
  by_source: Record<string, string>;
}

export interface ProjectFinancials {
  budget: {
    planned_budget: string;
    actual_cost: string;
    remaining_budget: string;
    budget_variance: string;
    over_budget: boolean;
    utilization_percent: number;
  };
  profitability: {
    revenue: string;
    cost: string;
    profit: string;
    margin_percent: number;
  };
  earned_value: {
    cpi: number;
    spi: number;
    cost_variance: string;
    schedule_variance: string;
    estimate_at_completion: string;
    [field: string]: unknown;
  };
  progress_percent: number;
  task_count: number;
  completed_tasks: number;
}

export interface GanttBar {
  id: string;
  start: string;
  finish: string;
  float: number;
  critical: boolean;
  [field: string]: unknown;
}

export interface ProjectSchedule {
  project_duration: number;
  critical_task_ids: string[];
  total_float: number;
  earliest_start?: string;
  earliest_finish?: string;
  gantt: GanttBar[];
}

export interface ResourceUtilizationRow {
  employee: string;
  total_percent: number;
  over_allocated: boolean;
  available_percent: number;
  [field: string]: unknown;
}

export interface ResourceUtilization {
  utilization: ResourceUtilizationRow[];
  conflicts: { employee: string; [field: string]: unknown }[];
}

export interface ResourceCapacityRow {
  employee: string;
  allocated_hours: number;
  available_hours: number;
  over_capacity: boolean;
  [field: string]: unknown;
}

export interface ResourceCapacity {
  capacity: ResourceCapacityRow[];
}

export const projectsApi = {
  /** Ensure the PRJ-/TSK- gapless number sequences exist (admin). */
  setup: () => apiSend<{ detail: string }>(`${P}/setup/`, "POST"),

  /** Create a project document; project & task get a gapless `number` auto-allocated. Body = field-slug dict. */
  createDocument: (entitySlug: ProjectEntitySlug, data: Record<string, unknown>) =>
    apiSend<ProjectRecord>(`${P}/${entitySlug}/`, "POST", data),

  // ── project lifecycle ────────────────────────────────────────────────────────
  startProject: (recordId: string) => apiSend<ProjectRecord>(`${P}/projects/${recordId}/start/`, "POST"),
  completeProject: (recordId: string) => apiSend<ProjectRecord>(`${P}/projects/${recordId}/complete/`, "POST"),
  /** Approve the project budget (admin). */
  approveBudget: (recordId: string) => apiSend<ProjectRecord>(`${P}/projects/${recordId}/budget/approve/`, "POST"),
  /** Snapshot the project baseline (schedule + budget). */
  baselineProject: (recordId: string) => apiSend<ProjectRecord>(`${P}/projects/${recordId}/baseline/`, "POST"),

  // ── document lifecycle (by record id) ─────────────────────────────────────────
  completeTask: (recordId: string) => apiSend<ProjectRecord>(`${P}/tasks/${recordId}/complete/`, "POST"),
  completeMilestone: (recordId: string) => apiSend<ProjectRecord>(`${P}/milestones/${recordId}/complete/`, "POST"),
  approveTimesheet: (recordId: string) => apiSend<ProjectRecord>(`${P}/timesheets/${recordId}/approve/`, "POST"),
  approveExpense: (recordId: string) => apiSend<ProjectRecord>(`${P}/expenses/${recordId}/approve/`, "POST"),
  approveChangeRequest: (recordId: string) =>
    apiSend<ProjectRecord>(`${P}/change-requests/${recordId}/approve/`, "POST"),
  approveDeliverable: (recordId: string) =>
    apiSend<ProjectRecord>(`${P}/deliverables/${recordId}/approve/`, "POST"),

  // ── native cost-rollup engine ─────────────────────────────────────────────────
  listCostEntries: (projectRecordId: string) =>
    apiGet<CostEntry[]>(`${P}/cost-entries/?project_record_id=${encodeURIComponent(projectRecordId)}`),

  /** Post a cost entry against a project (admin). */
  postCost: (data: {
    project_record_id: string;
    source: CostSource;
    amount: string;
    description: string;
    entry_date: string;
  }) => apiSend<CostEntry>(`${P}/cost-entries/`, "POST", data),

  /** Roll posted cost entries onto the project; returns the rolled-up totals. */
  rollupProject: (recordId: string) => apiSend<RollupResult>(`${P}/projects/${recordId}/rollup/`, "POST"),

  // ── native financials / EVM ───────────────────────────────────────────────────
  financials: (recordId: string) => apiGet<ProjectFinancials>(`${P}/projects/${recordId}/financials/`),

  // ── native scheduling / critical path ─────────────────────────────────────────
  schedule: (recordId: string) => apiGet<ProjectSchedule>(`${P}/projects/${recordId}/schedule/`),

  // ── native resources / capacity ───────────────────────────────────────────────
  utilization: () => apiGet<ResourceUtilization>(`${P}/resources/utilization/`),
  capacity: (weeklyHours = 40) =>
    apiGet<ResourceCapacity>(`${P}/resources/capacity/?weekly_hours=${encodeURIComponent(weeklyHours)}`),
};

export { apiGet };
