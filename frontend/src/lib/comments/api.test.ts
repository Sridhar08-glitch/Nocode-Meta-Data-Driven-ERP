import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { commentsApi, mentionToken } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("commentsApi", () => {
  it("builds the backend mention token", () => {
    expect(mentionToken("3f2504e0-4f89-41d3-9a0c-0305e82c3301")).toBe("@[3f2504e0-4f89-41d3-9a0c-0305e82c3301]");
  });

  it("lists, creates (with parent), edits, deletes, pins/unpins under the record path", () => {
    commentsApi.list("deals", "r1");
    commentsApi.create("deals", "r1", { body: "hi @[u1]", parent_id: "c0" });
    commentsApi.edit("deals", "r1", "c1", "edited");
    commentsApi.remove("deals", "r1", "c1");
    commentsApi.pin("deals", "r1", "c1");
    commentsApi.unpin("deals", "r1", "c1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/deals/r1/comments/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/deals/r1/comments/", "POST", { body: "hi @[u1]", parent_id: "c0" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/deals/r1/comments/c1/", "PATCH", { body: "edited" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/deals/r1/comments/c1/", "DELETE");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/deals/r1/comments/c1/pin/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/deals/r1/comments/c1/unpin/", "POST");
  });
});
