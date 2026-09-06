/**
 * Dependency & Impact Analysis client (Phase P2.14) — change-safety tooling over
 * `/api/v1/dependency/` (backend done). The analyzable object-type list is DATA-DRIVEN
 * (`/object-types/`) — never hardcode it so a future backend type appears automatically.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface RiskInfo {
  level: RiskLevel;
  count: number;
  exact: number;
  has_automation: boolean;
  score: number;
}

/** A single object that depends on (references) the analyzed object. */
export interface Dependent {
  type: string;
  name: string;
  detail: string;
  approximate: boolean;
  id: string | null;
}

export interface AnalyzeResult {
  object_type: string;
  object_id: string;
  name: string;
  used_by_count: number;
  by_type: Record<string, number>;
  dependents: Dependent[];
  risk: RiskInfo;
}

export interface SafeDeleteResult extends AnalyzeResult {
  action: "delete";
  safe: boolean;
  message: string;
}

export interface GraphNode {
  id: string;
  object_type: string;
  object_id: string;
  name: string;
  approximate?: boolean;
}
export interface GraphEdge {
  from: string;
  to: string;
  detail: string;
}
export interface DependencyGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ChangePreviewResult {
  direct_impact: number;
  indirect_impact: number;
  direct: Dependent[];
  risk: RiskInfo;
}

export interface PromotionObjectInput {
  object_type: string;
  object_id: string;
}
export interface PromotionObjectResult {
  object_type: string;
  object_id: string;
  name: string;
  used_by_count: number;
  risk: RiskInfo;
}
export interface PromotionPrecheckResult {
  blocked: boolean;
  decision: string;
  objects: PromotionObjectResult[];
}

export interface ExecutiveSummary {
  totals: {
    entities: number;
    fields: number;
    reports: number;
    dashboards: number;
    workflows: number;
  };
  recent_analyses: { object_type: string; used_by: number; risk: RiskLevel; at: string }[];
  high_risk_recent: number;
}

const D = "/api/v1/dependency";
const qs = (params: Record<string, string | number>) =>
  Object.entries(params)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join("&");

export const dependencyApi = {
  objectTypes: () => apiGet<{ object_types: string[] }>(`${D}/object-types/`),
  analyze: (objectType: string, objectId: string) =>
    apiGet<AnalyzeResult>(`${D}/analyze/?${qs({ object_type: objectType, object_id: objectId })}`),
  graph: (objectType: string, objectId: string, depth = 2) =>
    apiGet<DependencyGraph>(
      `${D}/graph/?${qs({ object_type: objectType, object_id: objectId, depth })}`,
    ),
  safeDelete: (objectType: string, objectId: string) =>
    apiGet<SafeDeleteResult>(
      `${D}/safe-delete/?${qs({ object_type: objectType, object_id: objectId })}`,
    ),
  changePreview: (body: { object_type: string; object_id: string; change: Record<string, unknown> }) =>
    apiSend<ChangePreviewResult>(`${D}/change-preview/`, "POST", body),
  promotionPrecheck: (body: { objects: PromotionObjectInput[] }) =>
    apiSend<PromotionPrecheckResult>(`${D}/promotion-precheck/`, "POST", body),
  executiveSummary: () => apiGet<ExecutiveSummary>(`${D}/executive-summary/`),
};
