/**
 * Environment Promotion / Release Management API (Phase P2.15).
 *
 * Hand-typed over the live `/api/v1/environments` surface (dynamic APIView responses).
 * A "promotion package" is a reviewed, risk-scored bundle of config objects promoted from
 * one environment to the next (DEV→TEST→UAT→PROD) via a merge commit, with separation-of-duties
 * approvals and a rollback point. Reads are member-level; mutations are admin-gated by the API.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type EnvType = "dev" | "test" | "uat" | "prod";

export interface Environment {
  id: string;
  name: string;
  env_type: EnvType;
  branch: string;
  sequence: number;
  is_production: boolean;
  status: string;
}

export type PackageStatus =
  | "draft"
  | "precheck"
  | "approved"
  | "executed"
  | "failed"
  | "rolled_back";

export type RiskLevel = "low" | "medium" | "high" | "critical";

/** Per-level risk counts (+ a `blocked` flag the precheck may surface). */
export interface RiskSummary {
  low?: number;
  medium?: number;
  high?: number;
  critical?: number;
  blocked?: number;
}

/** Per-kind change set (entities/fields/rules/roles/permissions), mirroring the config-vcs diff. */
export interface PackageDiffEntry {
  added: Record<string, unknown>[];
  removed: Record<string, unknown>[];
  modified: { before: Record<string, unknown>; after: Record<string, unknown> }[];
}
export type PackageDiff = Record<string, PackageDiffEntry>;

export interface ObjectRef {
  object_type: string;
  object_id: string;
}

export interface PromotionApproval {
  role: string;
  approver_id: string | null;
  decision: string;
  created_at?: string;
}

export interface PromotionPackage {
  id: string;
  name: string;
  version: string;
  source_env_id: string;
  target_env_id: string;
  status: PackageStatus;
  object_refs: ObjectRef[];
  diff: PackageDiff;
  risk_summary: RiskSummary;
  precheck: Record<string, unknown> | null;
  package_hash: string;
  merge_commit_sha: string | null;
  created_by: string | null;
  approved_by: string | null;
  executed_by: string | null;
  started_at: string | null;
  ended_at: string | null;
  approvals?: PromotionApproval[];
}

export interface PromotionDashboard {
  by_status: Record<string, number>;
  pending: number;
  approved: number;
  rollbacks: number;
  success_rate: number;
  risk_distribution: Record<RiskLevel, number>;
  release_velocity: number;
}

export interface DryRunResult {
  dry_run: true;
  would_merge: boolean;
  target_sha_before: string | null;
  risk: RiskSummary;
  diff: PackageDiff;
}

export interface ExecuteResult {
  status: "executed" | "failed";
  merge_commit?: string;
  rollback_point?: string;
  conflicts?: unknown[];
}

export type ExecuteResponse = DryRunResult | ExecuteResult;

export interface CreatePackageInput {
  source_env_id: string;
  target_env_id: string;
  name: string;
  objects: ObjectRef[];
}

const BASE = "/api/v1/environments";

export const environmentsApi = {
  list: () => apiGet<Environment[]>(`${BASE}/`),
  /** Ensure/provision the 4 environments (admin); returns the list. */
  ensure: () => apiSend<Environment[]>(`${BASE}/`, "POST", {}),

  packages: (status?: string) =>
    apiGet<PromotionPackage[]>(
      `${BASE}/packages/${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),
  createPackage: (body: CreatePackageInput) =>
    apiSend<PromotionPackage>(`${BASE}/packages/`, "POST", body),
  package: (id: string) => apiGet<PromotionPackage>(`${BASE}/packages/${id}/`),
  approve: (id: string, role: string) =>
    apiSend<PromotionPackage>(`${BASE}/packages/${id}/approve/`, "POST", { role }),
  execute: (id: string, dryRun: boolean) =>
    apiSend<ExecuteResponse>(`${BASE}/packages/${id}/execute/`, "POST", { dry_run: dryRun }),
  rollback: (id: string) =>
    apiSend<PromotionPackage>(`${BASE}/packages/${id}/rollback/`, "POST", {}),

  dashboard: () => apiGet<PromotionDashboard>(`${BASE}/dashboard/`),
};
