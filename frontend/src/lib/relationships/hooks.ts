"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { relationshipsApi, type RelationshipCreate } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["relationships", ws] });
  return { ws, enabled: isReady && !!ws, invalidate };
}

export function useRelationships(entityId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["relationships", ws, entityId ?? "all"],
    queryFn: () => relationshipsApi.list(entityId),
    enabled,
    staleTime: 60_000,
  });
}

export function useCreateRelationship() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (data: RelationshipCreate) => relationshipsApi.create(data),
    onSuccess: invalidate,
  });
}

export function useDeleteRelationship() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (id: string) => relationshipsApi.remove(id),
    onSuccess: invalidate,
  });
}
