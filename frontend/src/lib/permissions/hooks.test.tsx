import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  permissionsApi: {
    listRoles: vi.fn(() => Promise.resolve([])),
    createRole: vi.fn(() => Promise.resolve({})),
    updateRole: vi.fn(() => Promise.resolve({})),
    deleteRole: vi.fn(() => Promise.resolve(null)),
    listPermissions: vi.fn(() => Promise.resolve([])),
    createPermission: vi.fn(() => Promise.resolve({})),
    updatePermission: vi.fn(() => Promise.resolve({})),
    deletePermission: vi.fn(() => Promise.resolve(null)),
    listFieldPermissions: vi.fn(() => Promise.resolve([])),
    createFieldPermission: vi.fn(() => Promise.resolve({})),
    updateFieldPermission: vi.fn(() => Promise.resolve({})),
    deleteFieldPermission: vi.fn(() => Promise.resolve(null)),
    listMaskingRules: vi.fn(() => Promise.resolve([])),
    createMaskingRule: vi.fn(() => Promise.resolve({})),
    updateMaskingRule: vi.fn(() => Promise.resolve({})),
    deleteMaskingRule: vi.fn(() => Promise.resolve(null)),
  },
}));

import { permissionsApi } from "./api";
import {
  useCreateFieldPermission,
  useCreateMaskingRule,
  useCreatePermission,
  useCreateRole,
  useDeleteFieldPermission,
  useDeleteMaskingRule,
  useDeletePermission,
  useDeleteRole,
  useFieldPermissions,
  useMaskingRules,
  usePermissions,
  useRoles,
  useUpdateFieldPermission,
  useUpdateMaskingRule,
  useUpdatePermission,
  useUpdateRole,
} from "./hooks";

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = "W";
  return { qc, wrapper: Wrapper };
}

beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  tenant.isReady = true;
  vi.clearAllMocks();
});

describe("permission query hooks", () => {
  it("fetch when scoped (roles/grants/field-perms/masking, with role filter)", async () => {
    const { wrapper } = wrap();
    const roles = renderHook(() => useRoles(), { wrapper });
    const grants = renderHook(() => usePermissions("r1"), { wrapper });
    const fps = renderHook(() => useFieldPermissions("r1"), { wrapper });
    const masks = renderHook(() => useMaskingRules("r1"), { wrapper });
    // also exercise the unfiltered (roleId === undefined) branch of each list
    const grantsAll = renderHook(() => usePermissions(), { wrapper });
    const fpsAll = renderHook(() => useFieldPermissions(), { wrapper });
    const masksAll = renderHook(() => useMaskingRules(), { wrapper });
    await waitFor(() => expect(roles.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(grants.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(fps.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(masks.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(grantsAll.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(fpsAll.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(masksAll.result.current.isSuccess).toBe(true));
    expect(permissionsApi.listRoles).toHaveBeenCalled();
    expect(permissionsApi.listPermissions).toHaveBeenCalledWith("r1");
    expect(permissionsApi.listPermissions).toHaveBeenCalledWith(undefined);
    expect(permissionsApi.listFieldPermissions).toHaveBeenCalledWith("r1");
    expect(permissionsApi.listMaskingRules).toHaveBeenCalledWith("r1");
    expect(permissionsApi.listMaskingRules).toHaveBeenCalledWith(undefined);
  });

  it("are disabled without a workspace", () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    const { result } = renderHook(() => useRoles(), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(permissionsApi.listRoles).not.toHaveBeenCalled();
  });
});

describe("permission mutation hooks", () => {
  it("each mutation calls its API method and invalidates the permissions root", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const run = async <V,>(hook: () => { mutateAsync: (a: V) => Promise<unknown> }, arg: V) => {
      const { result } = renderHook(hook, { wrapper });
      await act(async () => {
        await result.current.mutateAsync(arg);
      });
    };
    await run(useCreateRole, { name: "X" });
    await run(useUpdateRole, { id: "r1", data: { name: "Y" } });
    await run(useDeleteRole, "r1");
    await run(useCreatePermission, { role: "r1", resource_type: "entity", action: "read" });
    await run(useUpdatePermission, { id: "p1", data: { is_deny: true } });
    await run(useDeletePermission, "p1");
    await run(useCreateFieldPermission, { field_id: "f1", role_id: "r1" });
    await run(useUpdateFieldPermission, { id: "fp1", data: { can_read: false } });
    await run(useDeleteFieldPermission, "fp1");
    await run(useCreateMaskingRule, { field_id: "f1", role_id: "r1", mask_type: "full" });
    await run(useUpdateMaskingRule, { id: "m1", data: { mask_pattern: "4" } });
    await run(useDeleteMaskingRule, "m1");

    expect(permissionsApi.createRole).toHaveBeenCalledWith({ name: "X" });
    expect(permissionsApi.updateRole).toHaveBeenCalledWith("r1", { name: "Y" });
    expect(permissionsApi.deleteRole).toHaveBeenCalledWith("r1");
    expect(permissionsApi.createPermission).toHaveBeenCalled();
    expect(permissionsApi.updatePermission).toHaveBeenCalledWith("p1", { is_deny: true });
    expect(permissionsApi.deletePermission).toHaveBeenCalledWith("p1");
    expect(permissionsApi.createFieldPermission).toHaveBeenCalled();
    expect(permissionsApi.updateFieldPermission).toHaveBeenCalledWith("fp1", { can_read: false });
    expect(permissionsApi.deleteFieldPermission).toHaveBeenCalledWith("fp1");
    expect(permissionsApi.createMaskingRule).toHaveBeenCalled();
    expect(permissionsApi.updateMaskingRule).toHaveBeenCalledWith("m1", { mask_pattern: "4" });
    expect(permissionsApi.deleteMaskingRule).toHaveBeenCalledWith("m1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["permissions", "acme"] });
  });
});
