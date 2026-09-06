"use client";

import { useQuery } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { searchApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  return { ws: workspace?.slug ?? null, enabled: isReady && !!workspace };
}

/** Full-text search. Disabled until the query has ≥2 chars (keeps Cmd+K quiet while empty). */
export function useSearch(q: string, opts: { entity?: string; limit?: number } = {}) {
  const { ws, enabled } = useScope();
  const query = q.trim();
  return useQuery({
    queryKey: ["search", ws, query, opts.entity ?? null, opts.limit ?? 25],
    queryFn: () => searchApi.search(query, opts),
    enabled: enabled && query.length >= 2,
    staleTime: 10_000,
  });
}

export function useRecentSearches() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["search", ws, "recent"],
    queryFn: () => searchApi.recent(),
    enabled,
    staleTime: 30_000,
  });
}
