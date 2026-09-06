"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { certificationApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  return { ws, enabled: isReady && !!ws };
}

/** Full integration registry (workspace-independent data, but scoped key for cache hygiene). */
export function useIntegrationRegistry() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["certification", ws, "integrations"],
    queryFn: () => certificationApi.integrations(),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useModuleHealth() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["certification", ws, "health"],
    queryFn: () => certificationApi.health(),
    enabled,
    staleTime: 30_000,
  });
}

export function useReadiness() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["certification", ws, "readiness"],
    queryFn: () => certificationApi.readiness(),
    enabled,
    staleTime: 30_000,
  });
}

export function useCertificationReport() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["certification", ws, "report"],
    queryFn: () => certificationApi.report(),
    enabled,
    staleTime: 30_000,
  });
}

export function useArchitectureValidation() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["certification", ws, "architecture"],
    queryFn: () => certificationApi.architecture(),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useChecklist() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["certification", ws, "checklist"],
    queryFn: () => certificationApi.checklist(),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useScenarios() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["certification", ws, "scenarios"],
    queryFn: () => certificationApi.scenarios(),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useRunScenario() {
  return useMutation({ mutationFn: (scenario: string) => certificationApi.runScenario(scenario) });
}

export function useRunAllScenarios() {
  return useMutation({ mutationFn: () => certificationApi.runAll() });
}
