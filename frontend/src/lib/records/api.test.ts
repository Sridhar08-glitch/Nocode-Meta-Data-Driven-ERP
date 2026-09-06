import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ ok: true })),
  apiSend: vi.fn(() => Promise.resolve({ ok: true })),
}));

import { apiGet, apiSend } from "@/lib/api/request";

import { listQuery, recordsApi } from "./api";

describe("recordsApi", () => {
  beforeEach(() => {
    vi.mocked(apiGet).mockClear();
    vi.mocked(apiSend).mockClear();
  });

  it("list hits the entity collection with the query string", () => {
    recordsApi.list("ticket", { limit: 10 });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/ticket/?limit=10");
  });

  it("list defaults to no query string", () => {
    recordsApi.list("ticket");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/ticket/");
  });

  it("get hits the detail path", () => {
    recordsApi.get("ticket", "abc");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/ticket/abc/");
  });

  it("create POSTs to the collection", () => {
    recordsApi.create("ticket", { name: "x" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/ticket/", "POST", { name: "x" });
  });

  it("update PATCHes the detail path", () => {
    recordsApi.update("ticket", "abc", { name: "y" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/ticket/abc/", "PATCH", { name: "y" });
  });

  it("remove DELETEs the detail path", () => {
    recordsApi.remove("ticket", "abc");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/ticket/abc/", "DELETE");
  });

  it("restore POSTs to the restore path", () => {
    recordsApi.restore("ticket", "abc");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/ticket/abc/restore/", "POST");
  });

  it("timeline / activity / sla hit their read paths", () => {
    recordsApi.timeline("ticket", "abc");
    recordsApi.activity("ticket", "abc");
    recordsApi.sla("ticket", "abc");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/ticket/abc/timeline/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/ticket/abc/activity/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/ticket/abc/sla/");
  });
});

describe("listQuery", () => {
  it("is empty for no params", () => {
    expect(listQuery({})).toBe("");
  });

  it("serialises sort with direction prefixes", () => {
    expect(listQuery({ sort: [{ field: "name", direction: "asc" }] })).toBe("?sort=name");
    expect(listQuery({ sort: [{ field: "created_at", direction: "desc" }] })).toBe("?sort=-created_at");
  });

  it("serialises limit and offset", () => {
    expect(listQuery({ limit: 25, offset: 50 })).toBe("?limit=25&offset=50");
  });

  it("JSON-encodes the filter", () => {
    const q = listQuery({ filter: { field: "status", op: "=", value: "open" } });
    expect(q).toContain("filter=");
    const value = new URLSearchParams(q.slice(1)).get("filter");
    expect(JSON.parse(value!)).toEqual({ field: "status", op: "=", value: "open" });
  });
});
