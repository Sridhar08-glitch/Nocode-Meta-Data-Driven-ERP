import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WorkspaceInvitation } from "@/lib/tenant/admin-api";

const useInvitations = vi.fn();
const inviteMutate = vi.fn().mockResolvedValue({});
const resendMutate = vi.fn().mockResolvedValue({});
const cancelMutate = vi.fn().mockResolvedValue({});

vi.mock("@/lib/tenant/admin-hooks", () => ({
  useInvitations: () => useInvitations(),
  useInvite: () => ({ mutateAsync: inviteMutate, isPending: false }),
  useResendInvitation: () => ({ mutateAsync: resendMutate }),
  useCancelInvitation: () => ({ mutateAsync: cancelMutate }),
}));

import { InvitationsPanel } from "./invitations-panel";

const inv = (over: Partial<WorkspaceInvitation> = {}): WorkspaceInvitation => ({
  id: "i1", email: "pending@acme.com", role: "member", status: "pending",
  invited_by: null, expires_at: "2030-01-01T00:00:00Z", responded_at: null,
  created_at: "2026-01-01T00:00:00Z", ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  useInvitations.mockReturnValue({ data: [inv()] });
});

describe("InvitationsPanel", () => {
  it("sends an invitation with email + role", async () => {
    render(<InvitationsPanel />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@acme.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send invite" }));
    await waitFor(() =>
      expect(inviteMutate).toHaveBeenCalledWith({ email: "new@acme.com", role: "member" }));
  });

  it("lists pending invitations and cancels one", async () => {
    render(<InvitationsPanel />);
    expect(screen.getByText("pending@acme.com")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(cancelMutate).toHaveBeenCalledWith("i1"));
  });

  it("resends a pending invitation", async () => {
    render(<InvitationsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Resend" }));
    await waitFor(() => expect(resendMutate).toHaveBeenCalledWith("i1"));
  });
});
