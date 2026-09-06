"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type BrandingSettings, brandingApi, type SMTPWrite } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, qc };
}

export function useBranding() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["branding-admin", ws], queryFn: () => brandingApi.get(), enabled, staleTime: 60_000 });
}
export function useUpdateBranding() {
  const { ws, qc } = useScope();
  return useMutation({
    mutationFn: (data: Partial<BrandingSettings>) => brandingApi.update(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["branding-admin", ws] });
      // the live theme is sourced from ["branding", slug] in TenantContext — refresh it too
      qc.invalidateQueries({ queryKey: ["branding", ws] });
    },
  });
}

export function useSmtpConfig() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["branding-admin", ws, "smtp"], queryFn: () => brandingApi.getSmtp(), enabled, staleTime: 60_000 });
}
export function useSaveSmtp() {
  const { ws, qc } = useScope();
  return useMutation({
    mutationFn: (data: SMTPWrite) => brandingApi.saveSmtp(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["branding-admin", ws, "smtp"] }),
  });
}
export function useTestSmtp() {
  return useMutation({ mutationFn: () => brandingApi.testSmtp() });
}
