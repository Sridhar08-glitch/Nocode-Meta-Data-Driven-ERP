"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { catalogApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, qc };
}

export function useBlueprints(params: { category?: string; search?: string } = {}) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["process-catalog", ws, "list", params],
    queryFn: () => catalogApi.list(params),
    enabled,
    staleTime: 60_000,
  });
}

export function useBlueprintPreview(id: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["process-catalog", ws, "preview", id],
    queryFn: () => catalogApi.preview(id!),
    enabled: enabled && !!id,
    staleTime: 60_000,
  });
}

export function useInstallBlueprint() {
  const { ws, qc } = useScope();
  return useMutation({
    mutationFn: (id: string) => catalogApi.install(id),
    onSuccess: () => {
      // a fresh install creates entities/workflows/rules/reports — refresh those caches
      qc.invalidateQueries({ queryKey: ["process-catalog", ws] });
      qc.invalidateQueries({ queryKey: ["entities", ws] });
      qc.invalidateQueries({ queryKey: ["workflows", ws] });
    },
  });
}
