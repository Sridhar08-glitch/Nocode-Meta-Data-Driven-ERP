/**
 * Enterprise Certification client (Phase P2.16) — read-only certification surface over
 * `/api/v1/certification/` plus the two simulation POSTs. The backend `apps/certification`
 * is orchestration-only: it reads existing engines and runs real service calls, never a
 * second engine. The UI mirrors that — it presents results, it does not compute them.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type HealthStatus = "healthy" | "warning" | "failed";
export type EngineStatus = "verified" | "warning" | "failed";
export type ReadinessStatus = "active" | "ready" | "not_installed";
export type IntegrationStatus = "certified" | "partial" | "deferred";
export type Verdict = "ENTERPRISE_CERTIFIED" | "READY_WITH_WARNINGS" | "NEEDS_ATTENTION";

export interface IntegrationEntry {
  id: string;
  source_module: string;
  target_module: string;
  service: string;
  trigger: string;
  event: string;
  accounting_impact: string;
  analytics_impact: string;
  audit_events: string[];
  notification_slugs: string[];
  idempotency_guard: string;
  status: IntegrationStatus;
}

export interface IntegrationRegistry {
  total_integrations: number;
  certified_count: number;
  integrations: IntegrationEntry[];
  by_source: Record<string, number>;
  by_target: Record<string, number>;
  checklist_count: number;
}

export interface ModuleHealth {
  modules: Record<string, { status: HealthStatus } & Record<string, unknown>>;
  overall: HealthStatus;
}

export interface ReadinessSummary {
  modules: Record<
    string,
    { status: ReadinessStatus; activity_7d: number; solution_slug: string | null }
  >;
  readiness_pct: number;
  total_modules: number;
  ready_or_active: number;
}

export interface ArchitectureValidation {
  engines: Record<string, { status: EngineStatus; location: string; note?: string; error?: string }>;
  overall: EngineStatus;
  verified_count: number;
  total_engines: number;
}

export interface ComplianceSection {
  name: string;
  passed: number;
  total: number;
  compliance_pct: number;
  items: { id: string; description?: string; status: string; module?: string }[];
}

export interface CertificationReport {
  report_title: string;
  generated_at: string;
  workspace_id: string;
  overall_readiness_score: number;
  status_counts?: Record<string, number>;
  status_overall?: string;
  overall_health: HealthStatus;
  readiness_pct: number;
  sections: ComplianceSection[];
  integration_health: {
    total_integrations: number;
    certified: number;
    partial: number;
    deferred: number;
    compliance_pct: number;
  };
  architecture_validation: ArchitectureValidation;
  module_health: ModuleHealth;
  executive_readiness: ReadinessSummary;
  recommendations: string[];
  verdict: Verdict;
}

export type ItemStatus = "COMPLETE" | "PARTIAL" | "NOT_IMPLEMENTED" | "OUT_OF_SCOPE";

export interface ChecklistItem {
  id: string;
  name: string;
  module: string;
  category?: string;
  status?: ItemStatus;
  tests?: string[];
  code_evidence?: string[];
}

export interface ScenarioMeta {
  key: string;
  name: string;
  description: string;
  modules: string[];
}

export interface SimulationStep {
  name: string;
  status: "pending" | "passed" | "failed" | "skipped";
  detail: string;
  error: string;
}

export interface SimulationResult {
  scenario: string;
  passed: boolean;
  steps: SimulationStep[];
  summary: Record<string, unknown>;
}

export interface RunAllResult {
  total_scenarios: number;
  passed: number;
  failed: number;
  pass_rate_pct: number;
  scenarios: Record<
    string,
    { passed: boolean; step_count: number; failed_steps: string[]; summary: Record<string, unknown> }
  >;
}

const C = "/api/v1/certification";

export const certificationApi = {
  integrations: () => apiGet<IntegrationRegistry>(`${C}/integrations/`),
  health: () => apiGet<ModuleHealth>(`${C}/health/`),
  readiness: () => apiGet<ReadinessSummary>(`${C}/readiness/`),
  report: () => apiGet<CertificationReport>(`${C}/report/`),
  architecture: () => apiGet<ArchitectureValidation>(`${C}/architecture/`),
  checklist: () => apiGet<{ total: number; checklist: ChecklistItem[] }>(`${C}/checklist/`),
  scenarios: () => apiGet<{ scenarios: ScenarioMeta[]; total: number }>(`${C}/simulations/`),
  runScenario: (scenario: string) =>
    apiSend<SimulationResult>(`${C}/simulations/run/`, "POST", { scenario }),
  runAll: () => apiSend<RunAllResult>(`${C}/simulations/run-all/`, "POST"),
};
