import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WorkspaceMember } from "@/lib/tenant/admin-api";

const useMembers = vi.fn();
const addMutate = vi.fn().mockResolvedValue({ created_user: true });
const suspendMutate = vi.fn().mockResolvedValue({});
const removeMutate = vi.fn().mockResolvedValue({});

vi.mock("@/lib/tenant/admin-hooks", () => ({
  useMembers: () => useMembers(),
  useAddMember: () => ({ mutateAsync: addMutate, isPending: false }),
  useAssignRole: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useRemoveMember: () => ({ mutateAsync: removeMutate }),
  useSuspendMember: () => ({ mutateAsync: suspendMutate }),
  useReactivateMember: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useResetMemberPassword: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useTransferOwnership: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
}));

const useTenant = vi.fn();
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => useTenant() }));

import { MembersAdmin } from "./members-admin";

const member = (over: Partial<WorkspaceMember> = {}): WorkspaceMember => ({
  id: "m1", user_id: "u1", email: "jane@acme.com", full_name: "Jane Doe",
  role: "member", status: "active", custom_role_id: null, joined_at: null,
  is_owner: false, ...over,
});

function asRole(role: string) {
  useTenant.mockReturnValue({ workspace: { slug: "acme", name: "Acme", role } });
}

beforeEach(() => {
  vi.clearAllMocks();
  useMembers.mockReturnValue({
    isError: false,
    data: [
      member({ id: "owner", email: "boss@acme.com", full_name: "Boss Person", role: "owner", is_owner: true }),
      member(),
    ],
    refetch: vi.fn(),
  });
  asRole("owner");
});

describe("MembersAdmin", () => {
  it("renders the roster", () => {
    render(<MembersAdmin />);
    expect(screen.getByText("boss@acme.com")).toBeInTheDocument();
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
  });

  it("adds a member with the entered email/name/role", async () => {
    render(<MembersAdmin />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@acme.com" } });
    fireEvent.change(screen.getByLabelText("Full name (optional)"), { target: { value: "New Hire" } });
    fireEvent.click(screen.getByRole("button", { name: "Add member" }));
    await waitFor(() => expect(addMutate).toHaveBeenCalledTimes(1));
    expect(addMutate).toHaveBeenCalledWith({ email: "new@acme.com", full_name: "New Hire", role: "member" });
  });

  it("suspends a non-owner member", async () => {
    render(<MembersAdmin />);
    fireEvent.click(screen.getByRole("button", { name: "Suspend" }));
    await waitFor(() => expect(suspendMutate).toHaveBeenCalledWith("m1"));
  });

  it("hides management for a plain member", () => {
    asRole("member");
    render(<MembersAdmin />);
    expect(screen.queryByRole("button", { name: "Add member" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Suspend" })).not.toBeInTheDocument();
  });

  it("offers Make owner only to the owner", () => {
    const { unmount } = render(<MembersAdmin />);
    expect(screen.getByRole("button", { name: "Make owner" })).toBeInTheDocument();
    unmount();
    asRole("admin");
    render(<MembersAdmin />);
    expect(screen.queryByRole("button", { name: "Make owner" })).not.toBeInTheDocument();
  });
});
