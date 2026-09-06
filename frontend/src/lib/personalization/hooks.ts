"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { EffectiveAppearance } from "@/lib/branding/apply";
import { useTenantStore } from "@/lib/tenant/store";

import { personalizationApi } from "./api";

/** Resolved effective appearance for the caller (used by the settings page + preview). */
export function useAppearance() {
  const slug = useTenantStore((s) => s.workspaceSlug);
  return useQuery({
    queryKey: ["appearance", slug],
    queryFn: personalizationApi.appearance,
    enabled: !!slug,
    staleTime: 5 * 60_000,
  });
}

/** The caller's raw overrides + the preference catalogue (drives the Appearance controls). */
export function usePreferences() {
  const slug = useTenantStore((s) => s.workspaceSlug);
  return useQuery({
    queryKey: ["preferences", slug],
    queryFn: personalizationApi.preferences,
    enabled: !!slug,
  });
}

function useInvalidatePersonalization() {
  const qc = useQueryClient();
  const slug = useTenantStore((s) => s.workspaceSlug);
  return () => {
    qc.invalidateQueries({ queryKey: ["appearance", slug] });
    qc.invalidateQueries({ queryKey: ["preferences", slug] });
  };
}

export function useSavePreferences() {
  const invalidate = useInvalidatePersonalization();
  return useMutation({
    mutationFn: (values: Partial<EffectiveAppearance>) => personalizationApi.savePreferences(values),
    onSuccess: invalidate,
  });
}

export function useResetPreferences() {
  const invalidate = useInvalidatePersonalization();
  return useMutation({
    mutationFn: (keys?: string[]) => personalizationApi.resetPreferences(keys),
    onSuccess: invalidate,
  });
}
