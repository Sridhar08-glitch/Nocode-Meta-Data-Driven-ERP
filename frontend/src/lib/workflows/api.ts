/**
 * Workflows client (Phase F1.10) — definitions, steps, edges, runs over `/api/v1/workflows/`.
 * Workflow "active state" is the `status` enum (no separate is_active). Lists are `{results,count}`.
 * `step_type` is validated server-side against the executor registry; we keep it a string and offer
 * a curated picker. Definitions stay fully serializable (the designer only ever emits this shape).
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type TriggerType =
  | "record_created"
  | "record_updated"
  | "record_deleted"
  | "field_changed"
  | "schedule"
  | "webhook"
  | "manual"
  | "stage_entered"
  | "sla_breached"
  | "form_submitted";

export type WorkflowStatus = "draft" | "active" | "paused" | "archived";
export type StepErrorMode = "stop" | "continue" | "retry";
export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled" | "timed_out";
export type StepRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped"
  | "waiting_approval";

export interface WorkflowDefinition {
  id: string;
  name: string;
  slug: string;
  description: string;
  trigger_type: TriggerType;
  trigger_config: Record<string, unknown>;
  entity_id: string | null;
  module_id: string | null;
  status: WorkflowStatus;
  version: number;
  is_system: boolean;
  max_concurrent_runs: number;
  timeout_seconds: number;
  retry_policy: Record<string, unknown>;
  run_count: number;
  error_count: number;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface WorkflowDefinitionWrite {
  name: string;
  slug?: string;
  description?: string;
  trigger_type: TriggerType;
  trigger_config?: Record<string, unknown>;
  entity_id?: string | null;
  module_id?: string | null;
  max_concurrent_runs?: number;
  timeout_seconds?: number;
  retry_policy?: Record<string, unknown>;
}

export interface WorkflowStep {
  id: string;
  workflow_id: string;
  step_type: string;
  name: string;
  config: Record<string, unknown>;
  position_x: number;
  position_y: number;
  is_entry: boolean;
  on_error: StepErrorMode;
  retry_config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
export interface WorkflowStepWrite {
  step_type: string;
  name: string;
  config?: Record<string, unknown>;
  position_x?: number;
  position_y?: number;
  is_entry?: boolean;
  on_error?: StepErrorMode;
  retry_config?: Record<string, unknown>;
}

export interface WorkflowEdge {
  id: string;
  workflow_id: string;
  source_step_id: string;
  target_step_id: string;
  condition_label: string;
  condition_expr: string;
}
export interface WorkflowEdgeWrite {
  source_step_id: string;
  target_step_id: string;
  condition_label?: string;
  condition_expr?: string;
}

export interface WorkflowStepRun {
  id: string;
  run_id: string;
  step_id: string;
  status: StepRunStatus;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  attempt_number: number;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown>;
  error_message: string;
}

export interface WorkflowRun {
  id: string;
  workflow_id: string;
  trigger_type: string;
  trigger_payload: Record<string, unknown>;
  entity_id: string | null;
  record_id: string | null;
  status: RunStatus;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  error_message: string;
  error_step_id: string | null;
  context: Record<string, unknown>;
  initiated_by: string | null;
  created_at: string;
  updated_at: string;
}
export interface WorkflowRunDetail extends WorkflowRun {
  step_runs: WorkflowStepRun[];
}

export interface Paged<T> {
  results: T[];
  count: number;
}

// ── picker options ───────────────────────────────────────────────────────────────────
export const TRIGGER_TYPE_OPTIONS: { value: TriggerType; label: string }[] = [
  { value: "record_created", label: "Record created" },
  { value: "record_updated", label: "Record updated" },
  { value: "record_deleted", label: "Record deleted" },
  { value: "field_changed", label: "Field changed" },
  { value: "stage_entered", label: "Stage entered" },
  { value: "sla_breached", label: "SLA breached" },
  { value: "form_submitted", label: "Form submitted" },
  { value: "schedule", label: "Schedule (cron)" },
  { value: "webhook", label: "Webhook" },
  { value: "manual", label: "Manual" },
];

/** Curated step types for the designer (the API accepts the full executor registry). */
export const STEP_TYPE_OPTIONS: { value: string; label: string; group: string }[] = [
  { value: "action_update_record", label: "Update record", group: "Actions" },
  { value: "action_create_record", label: "Create record", group: "Actions" },
  { value: "action_set_field", label: "Set field", group: "Actions" },
  { value: "action_send_email", label: "Send email", group: "Actions" },
  { value: "action_send_notification", label: "Send notification", group: "Actions" },
  { value: "action_send_webhook", label: "Send webhook", group: "Actions" },
  { value: "action_assign", label: "Assign", group: "Actions" },
  { value: "action_add_tag", label: "Add tag", group: "Actions" },
  { value: "condition", label: "Condition (branch)", group: "Logic" },
  { value: "wait", label: "Wait", group: "Logic" },
  { value: "approval", label: "Approval", group: "Logic" },
  { value: "loop", label: "Loop", group: "Logic" },
  { value: "parallel", label: "Parallel", group: "Logic" },
  { value: "join", label: "Join", group: "Logic" },
  { value: "nql_query", label: "NQL query", group: "Data" },
  { value: "transform", label: "Transform", group: "Data" },
  { value: "subworkflow", label: "Run sub-workflow", group: "Data" },
];

export const ON_ERROR_OPTIONS: { value: StepErrorMode; label: string }[] = [
  { value: "stop", label: "Stop the run" },
  { value: "continue", label: "Continue" },
  { value: "retry", label: "Retry" },
];

const base = "/api/v1/workflows";

export const workflowsApi = {
  // definitions
  listDefinitions: (params: { trigger_type?: string; status?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.trigger_type) qs.set("trigger_type", params.trigger_type);
    if (params.status) qs.set("status", params.status);
    const s = qs.toString();
    return apiGet<Paged<WorkflowDefinition>>(`${base}/definitions/${s ? `?${s}` : ""}`);
  },
  getDefinition: (id: string) => apiGet<WorkflowDefinition>(`${base}/definitions/${id}/`),
  createDefinition: (data: WorkflowDefinitionWrite) =>
    apiSend<WorkflowDefinition>(`${base}/definitions/`, "POST", data),
  updateDefinition: (id: string, data: Partial<WorkflowDefinitionWrite>) =>
    apiSend<WorkflowDefinition>(`${base}/definitions/${id}/`, "PATCH", data),
  deleteDefinition: (id: string) => apiSend<null>(`${base}/definitions/${id}/`, "DELETE"),
  activate: (id: string) => apiSend<WorkflowDefinition>(`${base}/definitions/${id}/activate/`, "POST"),
  pause: (id: string) => apiSend<WorkflowDefinition>(`${base}/definitions/${id}/pause/`, "POST"),
  duplicate: (id: string, slug?: string) =>
    apiSend<WorkflowDefinition>(`${base}/definitions/${id}/duplicate/`, "POST", slug ? { slug } : {}),

  // steps
  listSteps: (defId: string) => apiGet<Paged<WorkflowStep>>(`${base}/definitions/${defId}/steps/`),
  createStep: (defId: string, data: WorkflowStepWrite) =>
    apiSend<WorkflowStep>(`${base}/definitions/${defId}/steps/`, "POST", data),
  updateStep: (defId: string, stepId: string, data: Partial<WorkflowStepWrite>) =>
    apiSend<WorkflowStep>(`${base}/definitions/${defId}/steps/${stepId}/`, "PATCH", data),
  deleteStep: (defId: string, stepId: string) =>
    apiSend<null>(`${base}/definitions/${defId}/steps/${stepId}/`, "DELETE"),

  // edges
  listEdges: (defId: string) => apiGet<Paged<WorkflowEdge>>(`${base}/definitions/${defId}/edges/`),
  createEdge: (defId: string, data: WorkflowEdgeWrite) =>
    apiSend<WorkflowEdge>(`${base}/definitions/${defId}/edges/`, "POST", data),
  deleteEdge: (defId: string, edgeId: string) =>
    apiSend<null>(`${base}/definitions/${defId}/edges/${edgeId}/`, "DELETE"),

  // runs
  listRuns: (params: { workflow_id?: string; status?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.workflow_id) qs.set("workflow_id", params.workflow_id);
    if (params.status) qs.set("status", params.status);
    const s = qs.toString();
    return apiGet<Paged<WorkflowRun>>(`${base}/runs/${s ? `?${s}` : ""}`);
  },
  getRun: (runId: string) => apiGet<WorkflowRunDetail>(`${base}/runs/${runId}/`),
  cancelRun: (runId: string) => apiSend<WorkflowRun>(`${base}/runs/${runId}/cancel/`, "POST"),
  retryRun: (runId: string) => apiSend<WorkflowRun>(`${base}/runs/${runId}/retry/`, "POST"),
};
