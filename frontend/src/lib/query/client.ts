import { QueryClient } from "@tanstack/react-query";

/** Per-data-class staleTime (ms) — config rarely changes; records are live-ish. */
export const STALE_TIME = {
  metadata: 5 * 60_000, // entity/field/form schema — stable until a config publish
  config: 5 * 60_000, // branding, locale, flags
  records: 15_000, // record lists/details
  realtime: 0, // notifications, activity — always refetch/poll
} as const;

/**
 * TanStack Query defaults (Phase F1.2). No retry on 4xx (auth/permission/validation are
 * not transient). Per-data-class staleTime is applied at the hook level via STALE_TIME;
 * keys come from `lib/query/keys` (tenant + schemaVersion scoped).
 */
export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) => {
          const status = (error as { status?: number } | null)?.status;
          if (typeof status === "number" && status >= 400 && status < 500) return false;
          return failureCount < 2;
        },
        refetchOnWindowFocus: false,
      },
    },
  });
}
