"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type BackupType, backupsApi, type RestoreWrite, type RetentionWrite } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["backups", ws] }) };
}

export function useBackupJobs() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["backups", ws, "jobs"], queryFn: () => backupsApi.listJobs(), enabled, staleTime: 15_000 });
}
export function useCreateBackup() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (t: BackupType) => backupsApi.createJob(t), onSuccess: invalidate });
}
export function useDeleteBackup() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => backupsApi.deleteJob(id), onSuccess: invalidate });
}

export function useCreateRestore() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: RestoreWrite) => backupsApi.createRestore(d), onSuccess: invalidate });
}
export function useConfirmRestore() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, token }: { id: string; token: string }) => backupsApi.confirmRestore(id, token),
    onSuccess: invalidate,
  });
}

export function useRetentionPolicies() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["backups", ws, "retention"], queryFn: () => backupsApi.listRetention(), enabled, staleTime: 60_000 });
}
export function useCreateRetention() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: RetentionWrite) => backupsApi.createRetention(d), onSuccess: invalidate });
}
export function useDeleteRetention() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => backupsApi.deleteRetention(id), onSuccess: invalidate });
}
