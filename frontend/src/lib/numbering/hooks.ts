"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type NumberSequenceWrite, numberingApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => qc.invalidateQueries({ queryKey: ["numbering", ws] }),
  };
}

export function useNumberSequences() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["numbering", ws, "sequences"],
    queryFn: () => numberingApi.list(),
    enabled,
    staleTime: 30_000,
  });
}
export function useCreateSequence() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: NumberSequenceWrite) => numberingApi.create(data), onSuccess: invalidate });
}
export function useUpdateSequence() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<NumberSequenceWrite> }) => numberingApi.update(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteSequence() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => numberingApi.remove(id), onSuccess: invalidate });
}
export function useAllocateNumber() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => numberingApi.allocate(id), onSuccess: invalidate });
}
export function useResetSequence() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => numberingApi.reset(id), onSuccess: invalidate });
}
export function useSequenceAllocations(id: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["numbering", ws, "allocations", id],
    queryFn: () => numberingApi.allocations(id!),
    enabled: enabled && !!id,
    staleTime: 10_000,
  });
}
