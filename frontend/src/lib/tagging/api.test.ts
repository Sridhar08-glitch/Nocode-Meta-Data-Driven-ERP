import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { tagsApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("tagsApi", () => {
  it("lists/creates tags and attaches/detaches under /tags/records/", () => {
    tagsApi.list();
    tagsApi.create({ name: "VIP", slug: "vip", color: "#f00" });
    tagsApi.forRecord("rec1");
    tagsApi.attach("deals", "t1", "rec1");
    tagsApi.detach("t1", "rec1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/tags/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/tags/", "POST", { name: "VIP", slug: "vip", color: "#f00" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/tags/records/?record_id=rec1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/tags/records/", "POST", { entity_slug: "deals", tag_id: "t1", record_id: "rec1" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/tags/records/", "DELETE", { tag_id: "t1", record_id: "rec1" });
  });
});
