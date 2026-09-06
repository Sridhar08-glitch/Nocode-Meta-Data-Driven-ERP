"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  analyticsApi,
  type KpiInput,
  type ScorecardRole,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    qc,
    enabled: isReady && !!ws,
    /** Invalidate the KPI registry (+ evaluations/scorecards derive from it). */
    invalidateKpis: () => qc.invalidateQueries({ queryKey: ["analytics", "kpis", ws], exact: false }),
  };
}

/** Whether the caller may run privileged analytics writes (server gates regardless). */
export function useCanManageAnalytics(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

// ── setup ─────────────────────────────────────────────────────────────────────
export function useEnsureSetup() {
  const { invalidateKpis } = useScope();
  return useMutation({
    mutationFn: () => analyticsApi.setup(),
    onSuccess: () => invalidateKpis(),
  });
}

// ── KPI registry ────────────────────────────────────────────────────────────
export function useKpis(category?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["analytics", "kpis", ws, category ?? null],
    queryFn: () => analyticsApi.listKpis(category),
    enabled,
    staleTime: 30_000,
  });
}
export function useCreateKpi() {
  const { invalidateKpis } = useScope();
  return useMutation({
    mutationFn: (data: KpiInput) => analyticsApi.createKpi(data),
    onSuccess: () => invalidateKpis(),
  });
}
export function useUpdateKpi() {
  const { invalidateKpis } = useScope();
  return useMutation({
    mutationFn: (vars: { id: string; data: Partial<KpiInput> }) =>
      analyticsApi.updateKpi(vars.id, vars.data),
    onSuccess: () => invalidateKpis(),
  });
}
export function useDeleteKpi() {
  const { invalidateKpis } = useScope();
  return useMutation({
    mutationFn: (id: string) => analyticsApi.deleteKpi(id),
    onSuccess: () => invalidateKpis(),
  });
}

// ── evaluation ──────────────────────────────────────────────────────────────
export function useKpiValue(code: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["analytics", "kpis", ws, "value", code],
    queryFn: () => analyticsApi.kpiValue(code as string),
    enabled: enabled && !!code,
    staleTime: 15_000,
  });
}
export function useEvaluateAll(category?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["analytics", "kpis", ws, "evaluate", category ?? null],
    queryFn: () => analyticsApi.evaluateAll(category),
    enabled,
    staleTime: 15_000,
  });
}
export function useKpiTrend(code: string | undefined, limit = 12) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["analytics", "kpis", ws, "trend", code, limit],
    queryFn: () => analyticsApi.kpiTrend(code as string, limit),
    enabled: enabled && !!code,
  });
}

// ── scorecards ──────────────────────────────────────────────────────────────
export function useScorecard(role: ScorecardRole) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["analytics", "scorecards", ws, role],
    queryFn: () => analyticsApi.scorecard(role),
    enabled,
    staleTime: 15_000,
  });
}

// ── actions ─────────────────────────────────────────────────────────────────
export function useSnapshot() {
  const { invalidateKpis } = useScope();
  return useMutation({
    mutationFn: (period: string) => analyticsApi.snapshot(period),
    onSuccess: () => invalidateKpis(),
  });
}
export function useCheckAlerts() {
  return useMutation({ mutationFn: () => analyticsApi.checkAlerts() });
}
