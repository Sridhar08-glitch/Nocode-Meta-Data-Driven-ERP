import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({})) }));
import { apiGet } from "@/lib/api/request";
import { adminApi } from "./api";

beforeEach(() => vi.mocked(apiGet).mockClear());

describe("adminApi", () => {
  it("reads tenant health", () => {
    adminApi.health();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/admin/health/");
  });
});
