import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
  apiSend: vi.fn(() => Promise.resolve({})),
}));

import { apiGet, apiSend } from "@/lib/api/request";

import { savedViewsApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("savedViewsApi", () => {
  it("lists all and filtered by entity", () => {
    savedViewsApi.list();
    savedViewsApi.list("deals");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/saved-views/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/saved-views/?entity_slug=deals");
  });
  it("gets, creates, updates and deletes", () => {
    savedViewsApi.get("v1");
    savedViewsApi.create({ entity_slug: "deals", name: "Mine" });
    savedViewsApi.update("v1", { is_pinned: true });
    savedViewsApi.remove("v1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/saved-views/v1/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/saved-views/", "POST", {
      entity_slug: "deals",
      name: "Mine",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/saved-views/v1/", "PATCH", { is_pinned: true });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/saved-views/v1/", "DELETE");
  });
});
