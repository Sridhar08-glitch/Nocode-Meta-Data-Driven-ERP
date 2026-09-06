"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { portalApi } from "./api";
import { getPortalRefresh } from "./token-store";

/** The current portal session (via `me`); null/undefined until resolved. Realm-isolated. */
export function usePortalMe() {
  return useQuery({
    queryKey: ["portal", "me"],
    queryFn: () => portalApi.me(),
    enabled: typeof window !== "undefined" && !!getPortalRefresh(),
    retry: false,
    staleTime: 60_000,
  });
}

export function usePortalLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, email, password }: { slug: string; email: string; password: string }) => portalApi.login(slug, email, password),
    onSuccess: (user) => qc.setQueryData(["portal", "me"], user),
  });
}

export function usePortalLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => portalApi.logout(),
    onSuccess: () => qc.removeQueries({ queryKey: ["portal"] }),
  });
}

export function usePortalRecords(entitySlug: string) {
  return useQuery({
    queryKey: ["portal", "data", entitySlug],
    queryFn: () => portalApi.listRecords(entitySlug),
    enabled: !!entitySlug,
    staleTime: 15_000,
  });
}
