import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })) }));
import { apiGet } from "@/lib/api/request";
import { auditApi } from "./api";

beforeEach(() => vi.mocked(apiGet).mockClear());

describe("auditApi", () => {
  it("builds the filtered, paginated query", () => {
    auditApi.list({ resource_type: "record", action: "updated", limit: 25, offset: 50 });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/audit/?resource_type=record&action=updated&limit=25&offset=50");
  });
  it("defaults limit/offset", () => {
    auditApi.list();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/audit/?limit=50&offset=0");
  });
});
