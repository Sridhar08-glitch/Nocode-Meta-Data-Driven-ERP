/**
 * Admin client (Phase F3.1) — Tenant Health over `/api/v1/admin/health/` (backend Phase 1.31).
 * Owner/admin only. `api_latency_ms`/`queue`/`plan_limits`/`ai` are intentionally `null` server-side
 * (not yet instrumented; `ai` is null BY DESIGN per the no-AI constraint) — render them as "—".
 */
import { apiGet } from "@/lib/api/request";

export interface TenantHealth {
  workspace_id: string;
  generated_at: string;
  workflows: {
    total: number;
    completed: number;
    failed: number;
    running: number;
    queued: number;
    success_rate: number;
  };
  workflow_latency_ms: { p50: number | null; p95: number | null; p99: number | null; count: number };
  activity: { dau: number; wau: number; mau: number };
  records: { created_24h: number; created_7d: number; created_total: number };
  errors: { workflow_runs_24h: number; workflow_failures_24h: number; error_rate_24h: number };
  storage: { entity_count: number; row_count_estimate: number };
  api_latency_ms: null;
  queue: null;
  plan_limits: null;
  ai: null;
}

export const adminApi = {
  health: () => apiGet<TenantHealth>("/api/v1/admin/health/"),
};
