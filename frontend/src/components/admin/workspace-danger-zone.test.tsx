import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const archiveMutate = vi.fn().mockResolvedValue({});
const softDeleteMutate = vi.fn().mockResolvedValue({});
vi.mock("@/lib/tenant/admin-hooks", () => ({
  useArchiveWorkspace: () => ({ mutateAsync: archiveMutate }),
  useSoftDeleteWorkspace: () => ({ mutateAsync: softDeleteMutate }),
  useRequestHardDelete: () => ({ mutateAsync: vi.fn().mockResolvedValue({ confirmation_token: "t" }), isPending: false }),
  useConfirmHardDelete: () => ({ mutateAsync: vi.fn().mockResolvedValue({}), isPending: false }),
}));

const useTenant = vi.fn();
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => useTenant() }));

import { WorkspaceDangerZone } from "./workspace-danger-zone";

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...window.location, assign: vi.fn() },
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("WorkspaceDangerZone", () => {
  it("is hidden for non-owners", () => {
    useTenant.mockReturnValue({ workspace: { name: "Acme", role: "admin" } });
    const { container } = render(<WorkspaceDangerZone />);
    expect(container).toBeEmptyDOMElement();
  });

  it("archives for the owner", async () => {
    useTenant.mockReturnValue({ workspace: { name: "Acme", role: "owner" } });
    render(<WorkspaceDangerZone />);
    fireEvent.click(screen.getByRole("button", { name: "Archive workspace" }));
    await waitFor(() => expect(archiveMutate).toHaveBeenCalled());
  });

  it("soft-deletes after confirm", async () => {
    useTenant.mockReturnValue({ workspace: { name: "Acme", role: "owner" } });
    render(<WorkspaceDangerZone />);
    fireEvent.click(screen.getByRole("button", { name: "Delete (recoverable)" }));
    await waitFor(() => expect(softDeleteMutate).toHaveBeenCalled());
  });
});
