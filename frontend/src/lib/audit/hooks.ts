"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type AuditFilters, auditApi } from "./api";

export function useAuditLog(filters: AuditFilters = {}) {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  return useQuery({
    queryKey: ["audit", ws, filters],
    queryFn: () => auditApi.list(filters),
    enabled: isReady && !!ws,
    staleTime: 15_000,
    placeholderData: keepPreviousData,
  });
}
