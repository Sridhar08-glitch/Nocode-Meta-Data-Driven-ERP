"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type RecycleBinFilters, recycleBinApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["recyclebin", ws] }) };
}

export function useRecycleBin(filters: RecycleBinFilters = {}) {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["recyclebin", ws, filters], queryFn: () => recycleBinApi.list(filters), enabled, staleTime: 15_000 });
}
export function useRestoreEntry() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => recycleBinApi.restore(id), onSuccess: invalidate });
}
export function usePurgeEntry() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => recycleBinApi.purge(id), onSuccess: invalidate });
}
export function useBulkRestore() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (ids: string[]) => recycleBinApi.bulkRestore(ids), onSuccess: invalidate });
}
export function useBulkPurge() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (ids: string[]) => recycleBinApi.bulkPurge(ids), onSuccess: invalidate });
}
