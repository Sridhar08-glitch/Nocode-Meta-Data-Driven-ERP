"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  dashboardsApi,
  type DashboardWidgetWrite,
  type DashboardWrite,
  reportsApi,
  type ReportWrite,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidateReports: () => qc.invalidateQueries({ queryKey: ["reports", ws] }),
    invalidateDashboards: () => qc.invalidateQueries({ queryKey: ["dashboards", ws] }),
  };
}

// ── reports ───────────────────────────────────────────────────────────────────────
export function useReports(reportType?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["reports", ws, "list", reportType ?? "all"],
    queryFn: () => reportsApi.list(reportType),
    enabled,
    staleTime: 30_000,
  });
}
export function useReport(id: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["reports", ws, "detail", id],
    queryFn: () => reportsApi.get(id),
    enabled: enabled && !!id,
  });
}
export function useCreateReport() {
  const { invalidateReports } = useScope();
  return useMutation({ mutationFn: (d: ReportWrite) => reportsApi.create(d), onSuccess: invalidateReports });
}
export function useUpdateReport() {
  const { invalidateReports } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ReportWrite> }) => reportsApi.update(id, data),
    onSuccess: invalidateReports,
  });
}
export function useDeleteReport() {
  const { invalidateReports } = useScope();
  return useMutation({ mutationFn: (id: string) => reportsApi.remove(id), onSuccess: invalidateReports });
}
export function useRunReport(id: string) {
  return useMutation({ mutationFn: () => reportsApi.run(id) });
}
export function useValidateNql() {
  return useMutation({ mutationFn: (b: { nql_source?: string; nql_ast?: Record<string, unknown> }) => reportsApi.validateNql(b) });
}

// ── dashboards ────────────────────────────────────────────────────────────────────
export function useDashboards() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["dashboards", ws, "list"],
    queryFn: () => dashboardsApi.list(),
    enabled,
    staleTime: 30_000,
  });
}
export function useDashboard(id: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["dashboards", ws, "detail", id],
    queryFn: () => dashboardsApi.get(id),
    enabled: enabled && !!id,
  });
}
export function useCreateDashboard() {
  const { invalidateDashboards } = useScope();
  return useMutation({ mutationFn: (d: DashboardWrite) => dashboardsApi.create(d), onSuccess: invalidateDashboards });
}
export function useDeleteDashboard() {
  const { invalidateDashboards } = useScope();
  return useMutation({ mutationFn: (id: string) => dashboardsApi.remove(id), onSuccess: invalidateDashboards });
}
export function useRunDashboard(id: string) {
  return useMutation({ mutationFn: () => dashboardsApi.run(id) });
}
export function useCreateWidget(dashboardId: string) {
  const { invalidateDashboards } = useScope();
  return useMutation({
    mutationFn: (d: DashboardWidgetWrite) => dashboardsApi.createWidget(dashboardId, d),
    onSuccess: invalidateDashboards,
  });
}
export function useUpdateWidget(dashboardId: string) {
  const { invalidateDashboards } = useScope();
  return useMutation({
    mutationFn: ({ wid, data }: { wid: string; data: Partial<DashboardWidgetWrite> }) =>
      dashboardsApi.updateWidget(dashboardId, wid, data),
    onSuccess: invalidateDashboards,
  });
}
export function useDeleteWidget(dashboardId: string) {
  const { invalidateDashboards } = useScope();
  return useMutation({
    mutationFn: (wid: string) => dashboardsApi.deleteWidget(dashboardId, wid),
    onSuccess: invalidateDashboards,
  });
}
