import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [], total: 0 })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { searchApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("searchApi", () => {
  it("builds the search query with entity + paging", () => {
    searchApi.search("acme", { entity: "deals,contacts", limit: 8 });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/search/?q=acme&entity=deals%2Ccontacts&limit=8");
  });
  it("reads + clears recent searches", () => {
    searchApi.recent();
    searchApi.clearRecent();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/search/recent/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/search/recent/", "DELETE");
  });
});
