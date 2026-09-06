"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  type ApplicationWrite,
  type HomeLayoutWrite,
  type NavigationWrite,
  studioApi,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["studio", ws] }) };
}

const STALE = 60_000;

// ── applications ────────────────────────────────────────────────────────────────
export function useApplications() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["studio", ws, "apps"], queryFn: () => studioApi.listApps(), enabled, staleTime: STALE });
}
export function useAppSwitcher() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["studio", ws, "switcher"], queryFn: () => studioApi.switcher(), enabled, staleTime: STALE });
}
export function useCreateApp() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: ApplicationWrite) => studioApi.createApp(d), onSuccess: invalidate });
}
export function useUpdateApp() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ApplicationWrite> }) => studioApi.updateApp(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteApp() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => studioApi.deleteApp(id), onSuccess: invalidate });
}
export function usePublishApp() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => studioApi.publishApp(id), onSuccess: invalidate });
}

// ── home layouts ──────────────────────────────────────────────────────────────────
export function useHomeLayouts() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["studio", ws, "home"], queryFn: () => studioApi.listHome(), enabled, staleTime: STALE });
}
export function useResolvedHome(appId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["studio", ws, "home-resolve", appId ?? null],
    queryFn: () => studioApi.resolveHome(appId),
    enabled,
    staleTime: STALE,
  });
}
export function useCreateHome() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: HomeLayoutWrite) => studioApi.createHome(d), onSuccess: invalidate });
}
export function useUpdateHome() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<HomeLayoutWrite> }) => studioApi.updateHome(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteHome() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => studioApi.deleteHome(id), onSuccess: invalidate });
}
export function usePublishHome() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => studioApi.publishHome(id), onSuccess: invalidate });
}

// ── navigation ──────────────────────────────────────────────────────────────────
export function useNavigations() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["studio", ws, "nav"], queryFn: () => studioApi.listNav(), enabled, staleTime: STALE });
}
export function useResolvedNav(appId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["studio", ws, "nav-resolve", appId ?? null],
    queryFn: () => studioApi.resolveNav(appId),
    enabled,
    staleTime: STALE,
  });
}
export function useCreateNav() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: NavigationWrite) => studioApi.createNav(d), onSuccess: invalidate });
}
export function useUpdateNav() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<NavigationWrite> }) => studioApi.updateNav(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteNav() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => studioApi.deleteNav(id), onSuccess: invalidate });
}
export function usePublishNav() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => studioApi.publishNav(id), onSuccess: invalidate });
}
