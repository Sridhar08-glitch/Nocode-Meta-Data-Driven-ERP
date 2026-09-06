import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [] })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { portalAdminApi } from "./api";

beforeEach(() => { vi.mocked(apiGet).mockClear(); vi.mocked(apiSend).mockClear(); });

describe("portalAdminApi (custom admin, non-exempt path)", () => {
  it("uses the /portal-admin/ prefix for config, users, grants", () => {
    portalAdminApi.getConfig();
    portalAdminApi.updateConfig({ is_enabled: true });
    portalAdminApi.createUser({ email: "c@a.com", full_name: "C", password: "portalPW123", portal_type: "customer" });
    portalAdminApi.deleteUser("u1");
    portalAdminApi.createGrant({ entity_slug: "ticket", link_field: "customer", can_read: true });
    portalAdminApi.deleteGrant("g1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/portal-admin/config/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/portal-admin/config/", "PATCH", { is_enabled: true });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/portal-admin/users/", "POST", expect.objectContaining({ password: "portalPW123" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/portal-admin/users/u1/", "DELETE");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/portal-admin/grants/", "POST", expect.objectContaining({ entity_slug: "ticket" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/portal-admin/grants/g1/", "DELETE");
  });
});
