import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const createMutate = vi.fn().mockResolvedValue({ slug: "acme-mfg", role: "owner" });
vi.mock("@/lib/tenant/admin-hooks", () => ({
  useCreateWorkspace: () => ({ mutateAsync: createMutate, isPending: false }),
}));

const switchWorkspace = vi.fn();
vi.mock("@/lib/tenant/context", () => ({
  useTenant: () => ({ switchWorkspace }),
}));

import { CreateWorkspace } from "./create-workspace";

beforeEach(() => vi.clearAllMocks());

describe("CreateWorkspace", () => {
  it("creates a workspace and switches to it", async () => {
    const onCreated = vi.fn();
    render(<CreateWorkspace onCreated={onCreated} />);
    fireEvent.change(screen.getByLabelText("Workspace name"), { target: { value: "Acme Mfg" } });
    fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));
    await waitFor(() => expect(createMutate).toHaveBeenCalledWith({ name: "Acme Mfg" }));
    expect(switchWorkspace).toHaveBeenCalledWith("acme-mfg");
    expect(onCreated).toHaveBeenCalledWith("acme-mfg");
  });

  it("disables submit until a name is entered", () => {
    render(<CreateWorkspace />);
    expect(screen.getByRole("button", { name: "Create workspace" })).toBeDisabled();
  });
});
