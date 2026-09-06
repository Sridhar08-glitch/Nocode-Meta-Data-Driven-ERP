import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({})), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { catalogApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("catalogApi", () => {
  it("browses, previews, and installs", () => {
    catalogApi.list();
    catalogApi.list({ search: "onboarding", category: "hr" });
    catalogApi.preview("b1");
    catalogApi.install("b1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/process-catalog/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/process-catalog/?category=hr&search=onboarding");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/process-catalog/b1/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/process-catalog/b1/install/", "POST");
  });
});
