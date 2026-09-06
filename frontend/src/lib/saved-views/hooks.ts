"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { savedViewsApi, type SavedViewCreate, type SavedViewUpdate } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => qc.invalidateQueries({ queryKey: ["saved-views", ws] }),
  };
}

export function useSavedViews(entitySlug?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["saved-views", ws, entitySlug ?? "all"],
    queryFn: () => savedViewsApi.list(entitySlug),
    enabled,
    staleTime: 60_000,
  });
}

export function useCreateSavedView() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (data: SavedViewCreate) => savedViewsApi.create(data),
    onSuccess: invalidate,
  });
}

export function useUpdateSavedView() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SavedViewUpdate }) =>
      savedViewsApi.update(id, data),
    onSuccess: invalidate,
  });
}

export function useDeleteSavedView() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (id: string) => savedViewsApi.remove(id),
    onSuccess: invalidate,
  });
}
