import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Permission } from "@/lib/permissions/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const grantsQ = { isLoading: false, isError: false, data: [] as Permission[] };
const create = { mutateAsync: vi.fn(), isPending: false };
const del = { mutateAsync: vi.fn(), isPending: false };
vi.mock("@/lib/permissions/hooks", () => ({
  usePermissions: () => grantsQ,
  useCreatePermission: () => create,
  useDeletePermission: () => del,
}));

import { RoleGrants } from "./role-grants";

function grant(over: Partial<Permission> = {}): Permission {
  return {
    id: "p1",
    role: "r1",
    resource_type: "entity",
    resource_id: null,
    action: "read",
    is_deny: false,
    conditions: [],
    ...over,
  };
}

beforeEach(() => {
  grantsQ.isLoading = false;
  grantsQ.isError = false;
  grantsQ.data = [];
  create.isPending = false;
  del.isPending = false;
  create.mutateAsync.mockReset().mockResolvedValue({});
  del.mutateAsync.mockReset().mockResolvedValue(null);
  vi.clearAllMocks();
});

describe("RoleGrants", () => {
  it("renders loading and error states", () => {
    grantsQ.isLoading = true;
    const { rerender, container } = render(<RoleGrants roleId="r1" />);
    expect(container.querySelector(".h-40")).toBeTruthy();
    grantsQ.isLoading = false;
    grantsQ.isError = true;
    rerender(<RoleGrants roleId="r1" />);
    expect(screen.getByText("Couldn't load permissions")).toBeInTheDocument();
  });

  it("shows an empty state and opens the add dialog", () => {
    render(<RoleGrants roleId="r1" />);
    expect(screen.getByText("No permissions")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Add permission" })[0]);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("lists grants with allow/deny + condition badges", () => {
    grantsQ.data = [
      grant({ action: "*", is_deny: true, resource_id: "abc", conditions: [{ field: "owner_id", op: "=", value: "$me" }] }),
    ];
    render(<RoleGrants roleId="r1" />);
    expect(screen.getByText("deny")).toBeInTheDocument();
    expect(screen.getByText("1 condition(s)")).toBeInTheDocument();
    expect(screen.getByText("abc")).toBeInTheDocument();
  });

  it("deletes a grant", async () => {
    grantsQ.data = [grant()];
    render(<RoleGrants roleId="r1" />);
    fireEvent.click(screen.getByRole("button", { name: /Remove read on entity/ }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("p1"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("creates a grant with an ABAC condition", async () => {
    render(<RoleGrants roleId="r1" />);
    fireEvent.click(screen.getAllByRole("button", { name: "Add permission" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Add condition" }));
    fireEvent.change(screen.getByLabelText("Condition field 1"), { target: { value: "owner_id" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        role: "r1",
        resource_type: "entity",
        action: "read",
        conditions: [{ field: "owner_id", op: "=", value: "$user.id" }],
      }),
    );
  });

  it("surfaces a delete error", async () => {
    del.mutateAsync.mockRejectedValueOnce(new Error("x"));
    grantsQ.data = [grant()];
    render(<RoleGrants roleId="r1" />);
    fireEvent.click(screen.getByRole("button", { name: /Remove read on entity/ }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });
});
