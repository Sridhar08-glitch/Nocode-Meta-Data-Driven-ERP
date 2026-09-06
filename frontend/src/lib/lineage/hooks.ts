"use client";

import { useQuery } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { lineageApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  return { ws, enabled: isReady && !!ws };
}

export function useLineageNodes(nodeType?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["lineage", ws, "nodes", nodeType ?? null],
    queryFn: () => lineageApi.listNodes(nodeType),
    enabled,
    staleTime: 60_000,
  });
}

export function useUpstream(nodeId: string | null, maxDepth = 5) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["lineage", ws, "upstream", nodeId, maxDepth],
    queryFn: () => lineageApi.upstream(nodeId!, maxDepth),
    enabled: enabled && !!nodeId,
    staleTime: 60_000,
  });
}

export function useDownstream(nodeId: string | null, maxDepth = 5) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["lineage", ws, "downstream", nodeId, maxDepth],
    queryFn: () => lineageApi.downstream(nodeId!, maxDepth),
    enabled: enabled && !!nodeId,
    staleTime: 60_000,
  });
}
