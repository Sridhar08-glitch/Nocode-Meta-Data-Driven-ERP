"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { marketplaceApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => {
      qc.invalidateQueries({ queryKey: ["marketplace", ws] });
      qc.invalidateQueries({ queryKey: ["entities", ws] });
      qc.invalidateQueries({ queryKey: ["workflows", ws] });
    },
  };
}

export function usePlugins(params: { category?: string; search?: string } = {}) {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["marketplace", ws, "browse", params], queryFn: () => marketplaceApi.browse(params), enabled, staleTime: 60_000 });
}
export function usePluginDetail(id: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["marketplace", ws, "detail", id], queryFn: () => marketplaceApi.detail(id!), enabled: enabled && !!id, staleTime: 60_000 });
}
export function useInstalledPlugins() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["marketplace", ws, "installed"], queryFn: () => marketplaceApi.installed(), enabled, staleTime: 30_000 });
}
export function useInstallPlugin() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: ({ pluginId, versionId }: { pluginId: string; versionId: string }) => marketplaceApi.install(pluginId, versionId), onSuccess: invalidate });
}
export function useUninstallPlugin() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: ({ id, hard }: { id: string; hard?: boolean }) => marketplaceApi.uninstall(id, hard), onSuccess: invalidate });
}
export function useUpgradePlugin() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: ({ id, versionId }: { id: string; versionId: string }) => marketplaceApi.upgrade(id, versionId), onSuccess: invalidate });
}
export function useRollbackPlugin() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => marketplaceApi.rollback(id), onSuccess: invalidate });
}
