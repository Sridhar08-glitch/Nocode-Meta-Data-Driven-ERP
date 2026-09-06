"use client";

import { useQuery } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { adminApi } from "./api";

export function useTenantHealth() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  return useQuery({
    queryKey: ["admin", ws, "health"],
    queryFn: () => adminApi.health(),
    enabled: isReady && !!ws,
    staleTime: 30_000,
  });
}
