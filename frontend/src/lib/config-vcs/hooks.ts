"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { configVcsApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => {
      qc.invalidateQueries({ queryKey: ["config-vcs", ws] });
      // a publish/rollback changes live config → refresh all metadata too.
      qc.invalidateQueries({ queryKey: ["meta", ws] });
    },
  };
}

export function useCommits(branch = "main") {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["config-vcs", ws, "commits", branch],
    queryFn: () => configVcsApi.commits(branch),
    enabled,
    staleTime: 30_000,
  });
}

/** Publish the current draft: commit the live config snapshot. */
export function usePublish() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ message, branch }: { message: string; branch?: string }) =>
      configVcsApi.commit(message, branch),
    onSuccess: invalidate,
  });
}

export function useRollback() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (sha: string) => configVcsApi.rollback(sha),
    onSuccess: invalidate,
  });
}

/** Structural diff between two commit shas (Phase F3.3). Idle until both are picked + differ. */
export function useDiff(a: string | null, b: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["config-vcs", ws, "diff", a, b],
    queryFn: () => configVcsApi.diff(a!, b!),
    enabled: enabled && !!a && !!b && a !== b,
    staleTime: 30_000,
  });
}
