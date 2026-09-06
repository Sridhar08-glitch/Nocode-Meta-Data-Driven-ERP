"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchReadiness } from "./api";

/** Poll the system readiness probe. Not workspace-scoped — infra health is global. */
export function useReadiness() {
  return useQuery({
    queryKey: ["ops", "readiness"],
    queryFn: fetchReadiness,
    refetchInterval: 15_000,
    staleTime: 10_000,
  });
}
