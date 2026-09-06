import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })) }));
import { apiGet } from "@/lib/api/request";
import { activityApi } from "./api";

beforeEach(() => vi.mocked(apiGet).mockClear());

describe("activityApi", () => {
  it("builds the cross-entity feed query from filters", () => {
    activityApi.feed();
    activityApi.feed({ entity_slug: "deals", activity_type: "field_changed", date_from: "2026-01-01", limit: 50 });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/activity/feed/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/activity/feed/?entity_slug=deals&activity_type=field_changed&date_from=2026-01-01&limit=50");
  });

  it("reads per-record activity + the playback timeline", () => {
    activityApi.recordActivity("deals", "r1");
    activityApi.timeline("deals", "r1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/deals/r1/activity/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/deals/r1/timeline/");
  });
});
