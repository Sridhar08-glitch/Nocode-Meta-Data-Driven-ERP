"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { dependencyApi, type PromotionObjectInput } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  return { ws, enabled: isReady && !!ws };
}

/** Data-driven list of analyzable object types — the single source for the type picker. */
export function useObjectTypes() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["dependency", ws, "object-types"],
    queryFn: () => dependencyApi.objectTypes(),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useAnalyze(objectType: string | null, objectId: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["dependency", ws, "analyze", objectType, objectId],
    queryFn: () => dependencyApi.analyze(objectType!, objectId!),
    enabled: enabled && !!objectType && !!objectId,
    staleTime: 30_000,
  });
}

export function useDependencyGraph(objectType: string | null, objectId: string | null, depth = 2) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["dependency", ws, "graph", objectType, objectId, depth],
    queryFn: () => dependencyApi.graph(objectType!, objectId!, depth),
    enabled: enabled && !!objectType && !!objectId,
    staleTime: 30_000,
  });
}

export function useSafeDelete(objectType: string | null, objectId: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["dependency", ws, "safe-delete", objectType, objectId],
    queryFn: () => dependencyApi.safeDelete(objectType!, objectId!),
    enabled: enabled && !!objectType && !!objectId,
    staleTime: 30_000,
  });
}

export function useChangePreview() {
  return useMutation({
    mutationFn: (body: {
      object_type: string;
      object_id: string;
      change: Record<string, unknown>;
    }) => dependencyApi.changePreview(body),
  });
}

export function usePromotionPrecheck() {
  return useMutation({
    mutationFn: (objects: PromotionObjectInput[]) =>
      dependencyApi.promotionPrecheck({ objects }),
  });
}

export function useExecutiveSummary() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["dependency", ws, "executive-summary"],
    queryFn: () => dependencyApi.executiveSummary(),
    enabled,
    staleTime: 60_000,
  });
}
