"use client";

import { useQuery } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { activityApi, type ActivityFeedParams } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  return { ws: workspace?.slug ?? null, enabled: isReady && !!workspace };
}

export function useActivityFeed(params: ActivityFeedParams = {}) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["activity", ws, "feed", params],
    queryFn: () => activityApi.feed(params),
    enabled,
    staleTime: 15_000,
  });
}

export function useRecordTimeline(slug: string, recordId: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["activity", ws, "timeline", slug, recordId],
    queryFn: () => activityApi.timeline(slug, recordId),
    enabled: enabled && !!slug && !!recordId,
    staleTime: 30_000,
  });
}
