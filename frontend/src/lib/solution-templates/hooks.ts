"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { solutionTemplatesApi } from "./api";
import type { WizardSelection } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    qc,
    // a fresh install/uninstall provisions entities/applications/workflows — refresh those caches
    invalidate: () => {
      qc.invalidateQueries({ queryKey: ["solution-templates", ws] });
      qc.invalidateQueries({ queryKey: ["entities", ws] });
      qc.invalidateQueries({ queryKey: ["workflows", ws] });
      qc.invalidateQueries({ queryKey: ["applications", ws] });
    },
  };
}

export function useTemplates(params: { category?: string; search?: string } = {}) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["solution-templates", ws, "list", params],
    queryFn: () => solutionTemplatesApi.list(params),
    enabled,
    staleTime: 60_000,
  });
}

export function useTemplatePreview(id: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["solution-templates", ws, "preview", id],
    queryFn: () => solutionTemplatesApi.preview(id!),
    enabled: enabled && !!id,
    staleTime: 60_000,
  });
}

export function useLibrary() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["solution-templates", ws, "library"],
    queryFn: () => solutionTemplatesApi.library(),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useInstalledSolutions() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["solution-templates", ws, "installed"],
    queryFn: () => solutionTemplatesApi.installed(),
    enabled,
    staleTime: 30_000,
  });
}

export function useInstallTemplate() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (id: string) => solutionTemplatesApi.install(id),
    onSuccess: invalidate,
  });
}

export function useUninstallSolution() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, hard }: { id: string; hard?: boolean }) =>
      solutionTemplatesApi.uninstall(id, hard),
    onSuccess: invalidate,
  });
}

/* ----------------------- Create Solution Wizard (P2.4B) ----------------------- */

/** The full library + recommend presets driving every wizard choice. */
export function useWizardOptions() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["solution-templates", ws, "wizard-options"],
    queryFn: () => solutionTemplatesApi.wizardOptions(),
    enabled,
    staleTime: 5 * 60_000,
  });
}

/** Resolve the auto-included lookup dependencies for the chosen business objects. */
export function useResolveDependencies() {
  return useMutation({
    mutationFn: (businessObjects: string[]) =>
      solutionTemplatesApi.resolveDependencies(businessObjects),
  });
}

/** Validate + preview the assembled selection — nothing is installed. */
export function usePreviewSolution() {
  return useMutation({
    mutationFn: (selection: WizardSelection) => solutionTemplatesApi.previewSolution(selection),
  });
}

/** Provision the composed solution; refresh provisioning caches on success. */
export function useCreateSolution() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (selection: WizardSelection) => solutionTemplatesApi.createSolution(selection),
    onSuccess: invalidate,
  });
}
