"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { environmentsApi, type CreatePackageInput } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => qc.invalidateQueries({ queryKey: ["environments", ws] }),
  };
}

export function useEnvironments() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["environments", ws, "list"],
    queryFn: () => environmentsApi.list(),
    enabled,
    staleTime: 60_000,
  });
}

/** Ensure/provision the 4 environments (admin). */
export function useEnsureEnvironments() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: () => environmentsApi.ensure(),
    onSuccess: invalidate,
  });
}

export function usePackages(status?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["environments", ws, "packages", status ?? "all"],
    queryFn: () => environmentsApi.packages(status),
    enabled,
    staleTime: 30_000,
  });
}

export function useCreatePackage() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (body: CreatePackageInput) => environmentsApi.createPackage(body),
    onSuccess: invalidate,
  });
}

export function usePackage(id: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["environments", ws, "package", id],
    queryFn: () => environmentsApi.package(id!),
    enabled: enabled && !!id,
    staleTime: 15_000,
  });
}

export function useApprovePackage(id: string) {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (role: string) => environmentsApi.approve(id, role),
    onSuccess: invalidate,
  });
}

/** Execute or dry-run a package. `dry_run: true` is a no-op preview. */
export function useExecutePackage(id: string) {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (dryRun: boolean) => environmentsApi.execute(id, dryRun),
    // Only a real execute mutates state; invalidate either way (cheap, dry-run won't have changed it).
    onSuccess: invalidate,
  });
}

export function useRollbackPackage(id: string) {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: () => environmentsApi.rollback(id),
    onSuccess: invalidate,
  });
}

export function usePromotionDashboard() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["environments", ws, "dashboard"],
    queryFn: () => environmentsApi.dashboard(),
    enabled,
    staleTime: 30_000,
  });
}
