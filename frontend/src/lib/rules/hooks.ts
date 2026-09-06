"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type BusinessRuleWrite, rulesApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => qc.invalidateQueries({ queryKey: ["rules", ws] }),
  };
}

export function useRules(entityId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["rules", ws, "list", entityId ?? "all"],
    queryFn: () => rulesApi.list(entityId),
    enabled,
    staleTime: 30_000,
  });
}
export function useCreateRule() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: BusinessRuleWrite) => rulesApi.create(d), onSuccess: invalidate });
}
export function useUpdateRule() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<BusinessRuleWrite> }) => rulesApi.update(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteRule() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => rulesApi.remove(id), onSuccess: invalidate });
}
