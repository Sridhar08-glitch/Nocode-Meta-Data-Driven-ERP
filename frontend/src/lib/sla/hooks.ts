"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type BusinessHoursWrite, slaApi, type SLAPolicyWrite } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["sla", ws] }) };
}

export function useSlaPolicies() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["sla", ws, "policies"], queryFn: () => slaApi.listPolicies(), enabled, staleTime: 30_000 });
}
export function useCreatePolicy() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: SLAPolicyWrite) => slaApi.createPolicy(d), onSuccess: invalidate });
}
export function useUpdatePolicy() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<SLAPolicyWrite> }) => slaApi.updatePolicy(id, data),
    onSuccess: invalidate,
  });
}
export function useDeletePolicy() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => slaApi.deletePolicy(id), onSuccess: invalidate });
}

export function useBusinessHours() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["sla", ws, "business-hours"], queryFn: () => slaApi.listBusinessHours(), enabled, staleTime: 60_000 });
}
export function useCreateBusinessHours() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: BusinessHoursWrite) => slaApi.createBusinessHours(d), onSuccess: invalidate });
}
export function useUpdateBusinessHours() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<BusinessHoursWrite> }) => slaApi.updateBusinessHours(id, data),
    onSuccess: invalidate,
  });
}

export function useSlaDashboard() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["sla", ws, "dashboard"], queryFn: () => slaApi.dashboard(), enabled, staleTime: 30_000 });
}

// ── per-record SLA ────────────────────────────────────────────────────────────────
export function useRecordSla(slug: string, recordId: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["sla", ws, "record", slug, recordId],
    queryFn: () => slaApi.recordStatus(slug, recordId),
    enabled: enabled && !!slug && !!recordId,
    staleTime: 15_000,
  });
}
export function usePauseSla(slug: string, recordId: string) {
  const { ws } = useScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => slaApi.pause(slug, recordId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sla", ws, "record", slug, recordId] }),
  });
}
export function useResumeSla(slug: string, recordId: string) {
  const { ws } = useScope();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => slaApi.resume(slug, recordId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sla", ws, "record", slug, recordId] }),
  });
}
