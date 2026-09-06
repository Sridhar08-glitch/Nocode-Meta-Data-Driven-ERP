import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NumberSequence } from "@/lib/numbering/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const seqQ = { isLoading: false, isError: false, data: [] as NumberSequence[] };
const allocQ = { isLoading: false, data: { results: [] } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const allocate = { mutateAsync: vi.fn(() => Promise.resolve({ formatted: "INV-000001" })), isPending: false };
const reset = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };

vi.mock("@/lib/numbering/hooks", () => ({
  useNumberSequences: () => seqQ,
  useCreateSequence: () => create,
  useUpdateSequence: () => update,
  useDeleteSequence: () => del,
  useAllocateNumber: () => allocate,
  useResetSequence: () => reset,
  useSequenceAllocations: () => allocQ,
}));

import { NumberingManager } from "./numbering-manager";

const seq = (over: Partial<NumberSequence> = {}): NumberSequence => ({
  id: "s1", key: "invoice", name: "", description: "", prefix: "INV-", suffix: "",
  padding: 6, start_value: 1, increment: 1, reset_scope: "never", include_period_in_format: false,
  current_value: 0, period_key: "", is_active: true, is_system: false, created_at: "", updated_at: "", ...over,
});

beforeEach(() => {
  seqQ.data = [];
  for (const m of [create, update, del, allocate, reset]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("NumberingManager", () => {
  it("shows a formatted preview for each sequence", () => {
    seqQ.data = [seq()];
    render(<NumberingManager />);
    expect(screen.getByText("INV-000001")).toBeInTheDocument();
  });

  it("creates a sequence with the entered config", async () => {
    render(<NumberingManager />);
    fireEvent.click(screen.getAllByRole("button", { name: "New sequence" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Key"), { target: { value: "po" } });
    fireEvent.change(within(dialog).getByLabelText("Prefix"), { target: { value: "PO-" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ key: "po", prefix: "PO-" })),
    );
  });

  it("allocates a number from a sequence", async () => {
    seqQ.data = [seq()];
    render(<NumberingManager />);
    fireEvent.click(screen.getByRole("button", { name: "Allocate from invoice" }));
    await waitFor(() => expect(allocate.mutateAsync).toHaveBeenCalledWith("s1"));
  });

  it("resets a sequence", async () => {
    seqQ.data = [seq()];
    render(<NumberingManager />);
    fireEvent.click(screen.getByRole("button", { name: "Reset invoice" }));
    await waitFor(() => expect(reset.mutateAsync).toHaveBeenCalledWith("s1"));
  });

  it("hides delete for system sequences", () => {
    seqQ.data = [seq({ is_system: true })];
    render(<NumberingManager />);
    expect(screen.queryByRole("button", { name: "Delete invoice" })).not.toBeInTheDocument();
  });

  it("edit omits the immutable key from the update payload", async () => {
    seqQ.data = [seq()];
    render(<NumberingManager />);
    fireEvent.click(screen.getByRole("button", { name: "Edit invoice" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Prefix"), { target: { value: "BILL-" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(update.mutateAsync).toHaveBeenCalled());
    const payload = (update.mutateAsync.mock.calls[0] as unknown[])[0] as { id: string; data: Record<string, unknown> };
    expect(payload.id).toBe("s1");
    expect(payload.data).not.toHaveProperty("key");
    expect(payload.data.prefix).toBe("BILL-");
  });
});
