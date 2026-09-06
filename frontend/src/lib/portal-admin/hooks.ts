"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type PortalConfigWrite, type PortalGrantWrite, portalAdminApi, type PortalUserWrite } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["portal-admin", ws] }) };
}

export function usePortalConfig() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["portal-admin", ws, "config"], queryFn: () => portalAdminApi.getConfig(), enabled, staleTime: 60_000 });
}
export function useUpdatePortalConfig() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: PortalConfigWrite) => portalAdminApi.updateConfig(d), onSuccess: invalidate });
}

export function usePortalUsers() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["portal-admin", ws, "users"], queryFn: () => portalAdminApi.listUsers(), enabled, staleTime: 30_000 });
}
export function useCreatePortalUser() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: PortalUserWrite) => portalAdminApi.createUser(d), onSuccess: invalidate });
}
export function useDeletePortalUser() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => portalAdminApi.deleteUser(id), onSuccess: invalidate });
}

export function usePortalGrants() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["portal-admin", ws, "grants"], queryFn: () => portalAdminApi.listGrants(), enabled, staleTime: 30_000 });
}
export function useCreatePortalGrant() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: PortalGrantWrite) => portalAdminApi.createGrant(d), onSuccess: invalidate });
}
export function useDeletePortalGrant() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => portalAdminApi.deleteGrant(id), onSuccess: invalidate });
}
