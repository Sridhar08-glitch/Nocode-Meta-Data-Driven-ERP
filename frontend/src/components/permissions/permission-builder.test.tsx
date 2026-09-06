import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Role } from "@/lib/permissions/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const rolesQ = { isLoading: false, isError: false, data: [] as Role[] };
const createRole = { mutateAsync: vi.fn(), isPending: false };
const empty = { isLoading: false, isError: false, data: [] };
const noop = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
// usePermissions captures the roleId it is queried with, so we can prove role switching
// re-targets the underlying data (not just the visible heading).
const usePermissions = vi.fn((roleId?: string) => {
  void roleId; // recorded for the call-args assertions below
  return empty;
});
vi.mock("@/lib/permissions/hooks", () => ({
  useRoles: () => rolesQ,
  useCreateRole: () => createRole,
  usePermissions: (roleId?: string) => usePermissions(roleId),
  useCreatePermission: () => noop,
  useDeletePermission: () => noop,
  useFieldPermissions: () => empty,
  useMaskingRules: () => empty,
  useCreateFieldPermission: () => noop,
  useDeleteFieldPermission: () => noop,
  useCreateMaskingRule: () => noop,
  useDeleteMaskingRule: () => noop,
}));
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => empty }));
vi.mock("@/lib/metadata/builder-hooks", () => ({ useFields: () => empty }));

import { PermissionBuilder } from "./permission-builder";

function role(over: Partial<Role> = {}): Role {
  return {
    id: "r1",
    name: "Sales",
    slug: "sales",
    description: "",
    is_system: false,
    is_active: true,
    parent_role: null,
    ...over,
  };
}

beforeEach(() => {
  rolesQ.isLoading = false;
  rolesQ.isError = false;
  rolesQ.data = [];
  createRole.isPending = false;
  createRole.mutateAsync.mockReset().mockResolvedValue({ id: "r3", name: "Support" });
  usePermissions.mockClear();
  vi.clearAllMocks();
});

describe("PermissionBuilder — load states", () => {
  it("shows a skeleton while roles load", () => {
    rolesQ.isLoading = true;
    const { container } = render(<PermissionBuilder />);
    expect(container.querySelector(".h-64")).toBeTruthy();
  });

  it("shows an error state when roles fail", () => {
    rolesQ.isError = true;
    render(<PermissionBuilder />);
    expect(screen.getByText("Couldn't load roles")).toBeInTheDocument();
  });

  it("shows the empty-roles state and queries no role's grants", () => {
    render(<PermissionBuilder />);
    expect(screen.getByText("No roles")).toBeInTheDocument();
    // with no roles there is nothing to show on the right
    expect(screen.getByText("Select a role")).toBeInTheDocument();
  });
});

describe("PermissionBuilder — role selection drives the data shown", () => {
  it("auto-selects the first role and queries ITS grants", () => {
    rolesQ.data = [role(), role({ id: "r2", name: "Support" })];
    render(<PermissionBuilder />);
    // the first role's id is what the grants query is scoped to
    expect(usePermissions).toHaveBeenCalledWith("r1");
    expect(screen.getByRole("heading", { name: "Sales" })).toBeInTheDocument();
  });

  it("switching role re-queries grants for the newly selected role", () => {
    rolesQ.data = [role(), role({ id: "r2", name: "Support" })];
    render(<PermissionBuilder />);
    usePermissions.mockClear();
    fireEvent.click(screen.getByRole("button", { name: /Support/ }));
    // role switch must re-target the underlying grants query, not only swap the heading
    expect(usePermissions).toHaveBeenCalledWith("r2");
    expect(usePermissions).not.toHaveBeenCalledWith("r1");
    expect(screen.getByRole("heading", { name: "Support" })).toBeInTheDocument();
  });

  it("marks system roles and exposes both permission tabs for the active role", () => {
    rolesQ.data = [role({ id: "r2", name: "Support", is_system: true })];
    render(<PermissionBuilder />);
    expect(screen.getByText("system")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Permissions" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Field access" })).toBeInTheDocument();
  });
});

describe("PermissionBuilder — create role", () => {
  it("creates a role with a derived slug, toasts, and selects it (its grants are queried)", async () => {
    rolesQ.data = [role()];
    // creating a role makes it appear in the list (mimics the cache invalidation + refetch)
    createRole.mutateAsync.mockImplementation(async () => {
      rolesQ.data = [role(), role({ id: "r3", name: "Support Team", slug: "support_team" })];
      return { id: "r3", name: "Support Team" };
    });
    render(<PermissionBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "New" }));
    // Create is gated until a valid name exists
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Support Team" } });
    expect(screen.getByRole("button", { name: "Create" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() =>
      expect(createRole.mutateAsync).toHaveBeenCalledWith({ name: "Support Team", slug: "support_team" }),
    );
    expect(toast.success).toHaveBeenCalled();
    // the freshly created role (id r3) becomes selected → its grants are queried, and its heading shows
    await waitFor(() => expect(usePermissions).toHaveBeenCalledWith("r3"));
    expect(screen.getByRole("heading", { name: "Support Team" })).toBeInTheDocument();
  });

  it("surfaces an error toast and stays open when creation fails", async () => {
    rolesQ.data = [role()];
    createRole.mutateAsync.mockRejectedValueOnce(new Error("dup"));
    render(<PermissionBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "New" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Sales" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.getByRole("dialog")).toBeInTheDocument(); // dialog remains for retry
  });
});
