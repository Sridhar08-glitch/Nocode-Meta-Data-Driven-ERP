import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [] })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { marketplaceApi } from "./api";

beforeEach(() => { vi.mocked(apiGet).mockClear(); vi.mocked(apiSend).mockClear(); });

describe("marketplaceApi", () => {
  it("browses, installs, upgrades, uninstalls, rolls back", () => {
    marketplaceApi.browse({ search: "crm" });
    marketplaceApi.detail("p1");
    marketplaceApi.installed();
    marketplaceApi.install("p1", "v1");
    marketplaceApi.upgrade("i1", "v2");
    marketplaceApi.uninstall("i1", true);
    marketplaceApi.rollback("i1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/marketplace/plugins/?search=crm");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/marketplace/plugins/p1/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/marketplace/installed/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/marketplace/plugins/p1/install/", "POST", { version_id: "v1" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/marketplace/installed/i1/upgrade/", "POST", { version_id: "v2" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/marketplace/installed/i1/uninstall/", "POST", { hard: true });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/marketplace/installed/i1/rollback/", "POST");
  });
});
