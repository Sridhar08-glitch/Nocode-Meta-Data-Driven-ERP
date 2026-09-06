/**
 * Analytics & KPI Registry client (Phase P2.13) — a NATIVE engine over
 * `/api/v1/analytics/` (backend done). A KPI Registry that extends the reporting stack:
 * KPIs are either NQL-sourced (compile an NQL query + aggregate a value field) or native
 * (resolved by a server-side `native_key`). Each KPI carries target + warning/critical
 * thresholds and a direction (higher/lower better) so the server can grade good/warning/
 * critical. Executive scorecards group KPIs by role (CEO/CFO/COO/CHRO/CIO); snapshots
 * persist KPI values over time for trends. The evaluation, grading and snapshotting run
 * server-side; this client drives the registry + reads the graded values.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type KpiSourceType = "nql" | "native";
export type KpiAggregate = "sum" | "avg" | "count" | "min" | "max";
export type KpiDirection = "higher_better" | "lower_better";
export type KpiStatus = "good" | "warning" | "critical" | "unknown";
export type ScorecardRole = "ceo" | "cfo" | "coo" | "chro" | "cio";

export interface Kpi {
  id: string;
  code: string;
  name: string;
  description: string;
  category: string;
  source_type: KpiSourceType | string;
  nql_source: string;
  value_field: string;
  aggregate: KpiAggregate | string;
  native_key: string;
  target: string | null;
  warning_threshold: string | null;
  critical_threshold: string | null;
  direction: KpiDirection | string;
  unit: string;
  owner: string;
  refresh_strategy: string;
  is_active: boolean;
  is_system: boolean;
}

/** Payload to create/update a KPI. Source-specific fields are optional per source_type. */
export interface KpiInput {
  code: string;
  name: string;
  description?: string;
  category: string;
  source_type: KpiSourceType;
  nql_source?: string;
  value_field?: string;
  aggregate?: KpiAggregate;
  native_key?: string;
  target?: string | null;
  warning_threshold?: string | null;
  critical_threshold?: string | null;
  direction?: KpiDirection;
  unit?: string;
  owner?: string;
  refresh_strategy?: string;
  is_active?: boolean;
}

/** A graded KPI value — the evaluation of a KPI against its thresholds. */
export interface KpiValue {
  code: string;
  name: string;
  category: string;
  value: number | string | null;
  target: number | string | null;
  status: KpiStatus | string;
  variance: number | string | null;
  unit: string;
  available: boolean;
}

export interface KpiTrendPoint {
  value: number | string | null;
  status: KpiStatus | string;
  period: string;
  at: string;
}

export interface ScorecardSummary {
  good: number;
  warning: number;
  critical: number;
  unknown: number;
}

export interface Scorecard {
  role: string;
  kpis: KpiValue[];
  summary: ScorecardSummary;
}

const A = "/api/v1/analytics";

function qs(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const analyticsApi = {
  // setup — seed the standard KPI registry
  setup: () => apiSend<{ detail: string; created: number }>(`${A}/setup/`, "POST", {}),

  // KPI registry
  listKpis: (category?: string) => apiGet<Kpi[]>(`${A}/kpis/${qs({ category })}`),
  createKpi: (data: KpiInput) => apiSend<Kpi>(`${A}/kpis/`, "POST", data),
  updateKpi: (id: string, data: Partial<KpiInput>) =>
    apiSend<Kpi>(`${A}/kpis/${id}/`, "PATCH", data),
  deleteKpi: (id: string) => apiSend<void>(`${A}/kpis/${id}/`, "DELETE"),

  // evaluation
  kpiValue: (code: string) => apiGet<KpiValue>(`${A}/kpis/${code}/value/`),
  evaluateAll: (category?: string) =>
    apiGet<KpiValue[]>(`${A}/kpis/evaluate/${qs({ category })}`),
  kpiTrend: (code: string, limit = 12) =>
    apiGet<KpiTrendPoint[]>(`${A}/kpis/${code}/trend/${qs({ limit: String(limit) })}`),

  // scorecards
  scorecard: (role: ScorecardRole) => apiGet<Scorecard>(`${A}/scorecards/${role}/`),

  // actions
  snapshot: (period: string) =>
    apiSend<{ snapshotted: number }>(`${A}/snapshot/`, "POST", { period }),
  checkAlerts: () => apiSend<{ alerts: KpiValue[] }>(`${A}/alerts/check/`, "POST", {}),
};
