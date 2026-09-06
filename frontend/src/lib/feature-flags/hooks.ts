"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type FeatureFlagWrite, featureFlagsApi, type OverrideWrite } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["feature-flags", ws] }) };
}

export function useFeatureFlags() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["feature-flags", ws, "list"], queryFn: () => featureFlagsApi.list(), enabled, staleTime: 30_000 });
}
export function useCreateFlag() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: FeatureFlagWrite) => featureFlagsApi.create(d), onSuccess: invalidate });
}
export function useUpdateFlag() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<FeatureFlagWrite> }) => featureFlagsApi.update(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteFlag() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => featureFlagsApi.remove(id), onSuccess: invalidate });
}

export function useFlagOverrides(flagId: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["feature-flags", ws, "overrides", flagId],
    queryFn: () => featureFlagsApi.listOverrides(flagId!),
    enabled: enabled && !!flagId,
    staleTime: 30_000,
  });
}
export function useCreateOverride() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ flagId, data }: { flagId: string; data: OverrideWrite }) => featureFlagsApi.createOverride(flagId, data),
    onSuccess: invalidate,
  });
}
export function useDeleteOverride() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ flagId, overrideId }: { flagId: string; overrideId: string }) => featureFlagsApi.removeOverride(flagId, overrideId),
    onSuccess: invalidate,
  });
}
