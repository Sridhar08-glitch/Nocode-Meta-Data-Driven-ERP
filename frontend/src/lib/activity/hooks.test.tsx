import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  activityApi: {
    feed: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    timeline: vi.fn(() => Promise.resolve({ events: [], count: 0 })),
  },
}));
import { activityApi } from "./api";
import { useActivityFeed, useRecordTimeline } from "./hooks";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const W = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  W.displayName = "W";
  return { wrapper: W };
}
beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  vi.clearAllMocks();
});

describe("activity hooks", () => {
  it("fetches the feed with filters and the playback timeline", async () => {
    const { wrapper } = wrap();
    const feed = renderHook(() => useActivityFeed({ activity_type: "comment_added" }), { wrapper });
    const tl = renderHook(() => useRecordTimeline("deals", "r1"), { wrapper });
    await waitFor(() => expect(feed.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(tl.result.current.isSuccess).toBe(true));
    expect(activityApi.feed).toHaveBeenCalledWith({ activity_type: "comment_added" });
    expect(activityApi.timeline).toHaveBeenCalledWith("deals", "r1");
  });
  it("is idle without a workspace", () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    expect(renderHook(() => useActivityFeed(), { wrapper }).result.current.fetchStatus).toBe("idle");
  });
});
