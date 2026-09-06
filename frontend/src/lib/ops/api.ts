/**
 * System status client (Phase P1.6) — reads the unauthenticated readiness probe at
 * `/readyz/` (NOT under `/api/v1/`, NOT tenant-scoped). The probe returns 503 with a
 * per-component breakdown when a dependency is down, so we parse the JSON body on BOTH
 * 200 and 503 rather than throwing — the not-ready state is data to display, not an error.
 */
import { authFetch } from "@/lib/api/client";
import { API_BASE_URL } from "@/lib/api/config";

export interface ComponentCheck {
  ok: boolean;
  detail: string;
  latency_ms: number;
}
export interface Readiness {
  status: "ready" | "not_ready";
  checks: Record<string, ComponentCheck>;
}

export async function fetchReadiness(): Promise<Readiness> {
  const res = await authFetch(`${API_BASE_URL}/readyz/`);
  const text = await res.text();
  // 200 (ready) and 503 (not_ready) both carry the JSON report; anything else is a real error.
  if (res.status !== 200 && res.status !== 503) {
    throw new Error(`readiness probe failed: ${res.status}`);
  }
  return JSON.parse(text) as Readiness;
}
