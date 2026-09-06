"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useEntityKind } from "@/lib/metadata/hooks";
import { systemEntitiesApi } from "@/lib/system-entities/api";
import { useTenant } from "@/lib/tenant/context";

import { recordsApi, type ListParams, type RecordList } from "./api";

/** The record CRUD surface for one entity, chosen by source (B0.2): metadata → /data/{slug}/,
 *  system → /system-entities/{slug}/records/. Both expose the identical list/get/create/update/remove
 *  interface, so the hooks below are unchanged apart from picking the source. */
function useSource(entity: string) {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const { kind, ready } = useEntityKind(entity);
  const api =
    kind === "system"
      ? {
          list: systemEntitiesApi.records.list,
          get: systemEntitiesApi.records.get,
          create: systemEntitiesApi.records.create,
          update: systemEntitiesApi.records.update,
          remove: systemEntitiesApi.records.remove,
        }
      : {
          list: recordsApi.list,
          get: recordsApi.get,
          create: recordsApi.create,
          update: recordsApi.update,
          remove: recordsApi.remove,
        };
  return {
    ws,
    api,
    // Wait until the source is known so a system entity never mis-hits /data/{slug}/.
    enabled: isReady && !!ws && !!entity && ready && !!kind,
    base: ["data", ws, kind ?? "metadata", entity] as const,
  };
}

function useScope(entity: string) {
  return useSource(entity);
}

export function useRecords(entity: string, params: ListParams = {}) {
  const { base, enabled, api } = useScope(entity);
  return useQuery({
    queryKey: [...base, "list", params],
    queryFn: () => api.list(entity, params),
    enabled,
    staleTime: 15_000,
  });
}

export function useRecord(entity: string, id: string) {
  const { base, enabled, api } = useScope(entity);
  return useQuery({
    queryKey: [...base, "detail", id],
    queryFn: () => api.get(entity, id),
    enabled: enabled && !!id,
  });
}

export function useCreateRecord(entity: string) {
  const qc = useQueryClient();
  const { base, api } = useScope(entity);
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => api.create(entity, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...base, "list"] }),
  });
}

export function useUpdateRecord(entity: string) {
  const qc = useQueryClient();
  const { base, api } = useScope(entity);
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Record<string, unknown> }) =>
      api.update(entity, id, data),
    onSuccess: (_res, { id }) => {
      qc.invalidateQueries({ queryKey: [...base, "list"] });
      qc.invalidateQueries({ queryKey: [...base, "detail", id] });
    },
  });
}

export function useDeleteRecord(entity: string) {
  const qc = useQueryClient();
  const { base, api } = useScope(entity);
  return useMutation({
    mutationFn: (id: string) => api.remove(entity, id),
    // Optimistic: drop the row from every cached list page; roll back on error.
    onMutate: async (id: string) => {
      await qc.cancelQueries({ queryKey: [...base, "list"] });
      const snapshots = qc.getQueriesData<RecordList>({ queryKey: [...base, "list"] });
      for (const [key, data] of snapshots) {
        if (!data) continue;
        qc.setQueryData<RecordList>(key, {
          count: Math.max(0, data.count - 1),
          results: data.results.filter((r) => String(r.id) !== String(id)),
        });
      }
      return { snapshots };
    },
    onError: (_err, _id, ctx) => {
      ctx?.snapshots.forEach(([key, data]) => qc.setQueryData(key, data));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: [...base, "list"] }),
  });
}

export function useRestoreRecord(entity: string) {
  const qc = useQueryClient();
  const { base } = useScope(entity);
  return useMutation({
    mutationFn: (id: string) => recordsApi.restore(entity, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: [...base, "list"] }),
  });
}
