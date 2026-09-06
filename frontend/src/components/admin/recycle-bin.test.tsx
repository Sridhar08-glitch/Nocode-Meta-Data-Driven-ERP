import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { RecycleBinEntry } from "@/lib/recyclebin/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const binQ = { isLoading: false, isError: false, data: { results: [] as RecycleBinEntry[] } };
const restore = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const purge = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const bulkRestore = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const bulkPurge = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/recyclebin/hooks", () => ({
  useRecycleBin: () => binQ,
  useRestoreEntry: () => restore,
  usePurgeEntry: () => purge,
  useBulkRestore: () => bulkRestore,
  useBulkPurge: () => bulkPurge,
}));

import { RecycleBin } from "./recycle-bin";

const entry = (over: Partial<RecycleBinEntry> = {}): RecycleBinEntry => ({
  id: "e1", entity_id: "ent1", entity_slug: "lead", record_id: "r1", record_title: "Acme Lead",
  deleted_by: null, deleted_at: "2026-06-20T09:00:00Z", purge_after: "2026-07-20T09:00:00Z",
  cascade_entries: [], is_purged: false, purged_at: null, created_at: "", ...over,
});

beforeEach(() => {
  binQ.data = { results: [] };
  for (const m of [restore, purge, bulkRestore, bulkPurge]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("RecycleBin", () => {
  it("restores a record", async () => {
    binQ.data = { results: [entry()] };
    render(<RecycleBin />);
    expect(screen.getByText("Acme Lead")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Restore Acme Lead" }));
    await waitFor(() => expect(restore.mutateAsync).toHaveBeenCalledWith("e1"));
  });

  it("purges only after confirmation", async () => {
    binQ.data = { results: [entry()] };
    render(<RecycleBin />);
    fireEvent.click(screen.getByRole("button", { name: "Purge Acme Lead" }));
    expect(purge.mutateAsync).not.toHaveBeenCalled();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Purge permanently" }));
    await waitFor(() => expect(purge.mutateAsync).toHaveBeenCalledWith("e1"));
  });

  it("bulk-restores selected entries", async () => {
    binQ.data = { results: [entry(), entry({ id: "e2", record_title: "Beta Lead" })] };
    render(<RecycleBin />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Acme Lead" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Beta Lead" }));
    fireEvent.click(screen.getByRole("button", { name: "Restore" }));
    await waitFor(() => expect(bulkRestore.mutateAsync).toHaveBeenCalledWith(["e1", "e2"]));
  });
});
