import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BackupJob } from "@/lib/backups/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => ({ workspace: { id: "ws-current", slug: "acme" } }) }));

const jobsQ = { isLoading: false, isError: false, data: { results: [] as BackupJob[] } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const createRestore = { mutateAsync: vi.fn(() => Promise.resolve({ id: "r1", confirmation_token: "secret-token" })), isPending: false };
const confirmRestore = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/backups/hooks", () => ({
  useBackupJobs: () => jobsQ,
  useCreateBackup: () => create,
  useDeleteBackup: () => del,
  useCreateRestore: () => createRestore,
  useConfirmRestore: () => confirmRestore,
}));

import { BackupsPanel } from "./backups";

beforeEach(() => {
  jobsQ.data = { results: [] };
  for (const m of [create, del, createRestore, confirmRestore]) m.mutateAsync.mockClear();
  createRestore.mutateAsync.mockResolvedValue({ id: "r1", confirmation_token: "secret-token" });
  vi.clearAllMocks();
});

describe("BackupsPanel", () => {
  it("creates a backup", async () => {
    render(<BackupsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Create backup" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalledWith("full"));
  });

  it("blocks a restore that targets the source workspace", () => {
    render(<BackupsPanel />);
    fireEvent.change(screen.getByLabelText("Target workspace ID"), { target: { value: "ws-current" } });
    fireEvent.change(screen.getByLabelText("Target workspace slug"), { target: { value: "acme" } });
    expect(screen.getByText(/can't be overwritten/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create restore" })).toBeDisabled();
  });

  it("runs a PITR restore into an isolated target, then confirms with the one-time token", async () => {
    render(<BackupsPanel />);
    // switch to PITR
    fireEvent.click(screen.getByRole("combobox", { name: "Restore type" }));
    fireEvent.click(await screen.findByRole("option", { name: "Point-in-time" }));
    fireEvent.change(screen.getByLabelText("Target sequence"), { target: { value: "42" } });
    fireEvent.change(screen.getByLabelText("Target workspace ID"), { target: { value: "ws-sandbox" } });
    fireEvent.change(screen.getByLabelText("Target workspace slug"), { target: { value: "sandbox" } });
    fireEvent.click(screen.getByRole("button", { name: "Create restore" }));
    await waitFor(() => expect(createRestore.mutateAsync).toHaveBeenCalled());
    expect(createRestore.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ restore_type: "pitr", pitr_target_sequence: 42, target_workspace_id: "ws-sandbox" }),
    );
    // token surfaced; confirm dispatches it
    expect(await screen.findByText("secret-token")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm restore" }));
    await waitFor(() => expect(confirmRestore.mutateAsync).toHaveBeenCalledWith({ id: "r1", token: "secret-token" }));
  });
});
