import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve([])),
  apiSend: vi.fn(() => Promise.resolve({})),
}));

import { apiGet, apiSend } from "@/lib/api/request";

import { permissionsApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("permissionsApi roles", () => {
  it("CRUDs roles", () => {
    permissionsApi.listRoles();
    permissionsApi.createRole({ name: "Sales" });
    permissionsApi.updateRole("r1", { name: "Sales2" });
    permissionsApi.deleteRole("r1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/permissions/roles/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/roles/", "POST", { name: "Sales" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/roles/r1/", "PATCH", { name: "Sales2" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/roles/r1/", "DELETE");
  });
});

describe("permissionsApi grants", () => {
  it("lists with and without a role filter, and CRUDs", () => {
    permissionsApi.listPermissions();
    permissionsApi.listPermissions("r1");
    permissionsApi.createPermission({ role: "r1", resource_type: "entity", action: "read" });
    permissionsApi.updatePermission("p1", { is_deny: true });
    permissionsApi.deletePermission("p1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/permissions/permissions/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/permissions/permissions/?role=r1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/permissions/", "POST", {
      role: "r1",
      resource_type: "entity",
      action: "read",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/permissions/p1/", "PATCH", {
      is_deny: true,
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/permissions/p1/", "DELETE");
  });
});

describe("permissionsApi field-permissions", () => {
  it("lists (filtered) and CRUDs", () => {
    permissionsApi.listFieldPermissions("r1");
    permissionsApi.createFieldPermission({ field_id: "f1", role_id: "r1", can_read: false });
    permissionsApi.updateFieldPermission("fp1", { can_write: false });
    permissionsApi.deleteFieldPermission("fp1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/permissions/field-permissions/?role=r1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/field-permissions/", "POST", {
      field_id: "f1",
      role_id: "r1",
      can_read: false,
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/field-permissions/fp1/", "PATCH", {
      can_write: false,
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/field-permissions/fp1/", "DELETE");
  });
});

describe("permissionsApi masking-rules", () => {
  it("lists and CRUDs", () => {
    permissionsApi.listMaskingRules();
    permissionsApi.createMaskingRule({ field_id: "f1", role_id: "r1", mask_type: "full" });
    permissionsApi.updateMaskingRule("m1", { mask_pattern: "4" });
    permissionsApi.deleteMaskingRule("m1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/permissions/masking-rules/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/masking-rules/", "POST", {
      field_id: "f1",
      role_id: "r1",
      mask_type: "full",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/masking-rules/m1/", "PATCH", {
      mask_pattern: "4",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/permissions/masking-rules/m1/", "DELETE");
  });
});
