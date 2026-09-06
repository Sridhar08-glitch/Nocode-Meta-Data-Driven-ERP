"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  type ConnectorWrite,
  type InboundWrite,
  integrationsApi,
  type OAuthAppWrite,
  type SubscriptionWrite,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["integrations", ws] }) };
}

// ── outbound webhooks ──────────────────────────────────────────────────────────────
export function useSubscriptions() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["integrations", ws, "subs"], queryFn: () => integrationsApi.listSubs(), enabled, staleTime: 30_000 });
}
export function useCreateSub() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: SubscriptionWrite) => integrationsApi.createSub(d), onSuccess: invalidate });
}
export function useDeleteSub() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => integrationsApi.deleteSub(id), onSuccess: invalidate });
}
export function useTestSub() {
  return useMutation({ mutationFn: (id: string) => integrationsApi.testSub(id) });
}
export function useToggleSub() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, enable }: { id: string; enable: boolean }) => (enable ? integrationsApi.enableSub(id) : integrationsApi.disableSub(id)),
    onSuccess: invalidate,
  });
}
export function useDeliveries(id: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["integrations", ws, "deliveries", id],
    queryFn: () => integrationsApi.deliveries(id!),
    enabled: enabled && !!id,
    staleTime: 15_000,
  });
}

// ── inbound webhooks ──────────────────────────────────────────────────────────────
export function useInboundWebhooks() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["integrations", ws, "inbound"], queryFn: () => integrationsApi.listInbound(), enabled, staleTime: 30_000 });
}
export function useCreateInbound() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: InboundWrite) => integrationsApi.createInbound(d), onSuccess: invalidate });
}
export function useDeleteInbound() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => integrationsApi.deleteInbound(id), onSuccess: invalidate });
}
export function useRotateInbound() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => integrationsApi.rotateInbound(id), onSuccess: invalidate });
}

// ── connectors ──────────────────────────────────────────────────────────────────
export function useConnectors() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["integrations", ws, "connectors"], queryFn: () => integrationsApi.listConnectors(), enabled, staleTime: 30_000 });
}
export function useCreateConnector() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: ConnectorWrite) => integrationsApi.createConnector(d), onSuccess: invalidate });
}
export function useDeleteConnector() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => integrationsApi.deleteConnector(id), onSuccess: invalidate });
}
export function useTestConnector() {
  return useMutation({ mutationFn: (id: string) => integrationsApi.testConnector(id) });
}

// ── oauth apps ──────────────────────────────────────────────────────────────────
export function useOAuthApps() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["integrations", ws, "oauth"], queryFn: () => integrationsApi.listOAuth(), enabled, staleTime: 30_000 });
}
export function useCreateOAuth() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: OAuthAppWrite) => integrationsApi.createOAuth(d), onSuccess: invalidate });
}
export function useDeleteOAuth() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => integrationsApi.deleteOAuth(id), onSuccess: invalidate });
}
