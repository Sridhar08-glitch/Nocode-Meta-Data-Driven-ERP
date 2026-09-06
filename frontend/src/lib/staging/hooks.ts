"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  type DuplicateStrategy,
  type ExportFormat,
  exportApi,
  importApi,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, qc };
}

/** Poll a job while it's in a non-terminal state (parse/validate/import run async on Celery). */
const terminal = new Set(["awaiting_confirm", "completed", "failed", "cancelled"]);

export function useImportJob(id: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["import", ws, id],
    queryFn: () => importApi.get(id),
    enabled: enabled && !!id,
    refetchInterval: (q) => (q.state.data && terminal.has(q.state.data.status) ? false : 1500),
  });
}
export function useCreateImport() {
  const { ws, qc } = useScope();
  return useMutation({
    mutationFn: (opts: { file: File; entity_slug: string; duplicate_strategy?: DuplicateStrategy }) => importApi.create(opts),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["import", ws] }),
  });
}
export function useSetImportMapping(id: string) {
  const { ws, qc } = useScope();
  return useMutation({
    mutationFn: (mapping: Record<string, string | null>) => importApi.setMapping(id, mapping),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["import", ws, id] }),
  });
}
export function useImportPreview(id: string, enabledWhen: boolean) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["import", ws, id, "preview"],
    queryFn: () => importApi.preview(id),
    enabled: enabled && !!id && enabledWhen,
    staleTime: 5_000,
  });
}
export function useConfirmImport(id: string) {
  const { ws, qc } = useScope();
  return useMutation({
    mutationFn: () => importApi.confirm(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["import", ws, id] }),
  });
}

export function useCreateExport() {
  return useMutation({
    mutationFn: (data: { entity_slug?: string; nql_ast?: Record<string, unknown>; format?: ExportFormat }) => exportApi.create(data),
  });
}
export function useExportJob(id: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["export", ws, id],
    queryFn: () => exportApi.get(id),
    enabled: enabled && !!id,
    refetchInterval: (q) => (q.state.data && (q.state.data.status === "completed" || q.state.data.status === "failed") ? false : 1500),
  });
}
