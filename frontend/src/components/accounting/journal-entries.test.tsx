import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { JournalEntry, LedgerAccount } from "@/lib/ledger/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const entriesQ = { isLoading: false, isError: false, data: [] as JournalEntry[] };
const accountsQ = { isLoading: false, isError: false, data: [] as LedgerAccount[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const reverse = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };

vi.mock("@/lib/ledger/hooks", () => ({
  useJournalEntries: () => entriesQ,
  useLedgerAccounts: () => accountsQ,
  useCreateEntry: () => create,
  useReverseEntry: () => reverse,
}));

import { JournalEntries } from "./journal-entries";

const entry = (over: Partial<JournalEntry> = {}): JournalEntry => ({
  id: "e1", entry_number: "JE-000001", date: "2026-06-15", period: null, memo: "cash sale",
  currency: "", status: "posted", source_module: "manual", source_ref: "", posting_rule_key: "",
  posted_at: "2026-06-15T00:00:00Z", reverses: null, created_at: "",
  lines: [
    { account: "a1", account_code: "1000", account_name: "Cash", debit: "100.00", credit: "0.00" },
    { account: "a2", account_code: "4000", account_name: "Sales", debit: "0.00", credit: "100.00" },
  ],
  ...over,
});

beforeEach(() => {
  entriesQ.data = [];
  accountsQ.data = [];
  for (const m of [create, reverse]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("JournalEntries", () => {
  it("lists a posted entry with its number and reverses it", async () => {
    entriesQ.data = [entry()];
    render(<JournalEntries />);
    expect(screen.getByText("JE-000001")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reverse JE-000001" }));
    await waitFor(() => expect(reverse.mutateAsync).toHaveBeenCalledWith("e1"));
  });

  it("does not offer reverse on a draft entry", () => {
    entriesQ.data = [entry({ status: "draft", entry_number: "" })];
    render(<JournalEntries />);
    expect(screen.queryByRole("button", { name: /Reverse/ })).not.toBeInTheDocument();
  });

  it("enables Post only when debits equal credits", async () => {
    render(<JournalEntries />);
    fireEvent.click(screen.getAllByRole("button", { name: "New journal entry" })[0]);
    const dialog = await screen.findByRole("dialog");
    const post = within(dialog).getByRole("button", { name: "Post" });
    expect(post).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Line 1 debit"), { target: { value: "100" } });
    fireEvent.change(within(dialog).getByLabelText("Line 2 credit"), { target: { value: "60" } });
    expect(within(dialog).getByText("Unbalanced")).toBeInTheDocument();
    expect(post).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Line 2 credit"), { target: { value: "100" } });
    expect(within(dialog).getByText("Balanced")).toBeInTheDocument();
    expect(post).not.toBeDisabled();
  });

  it("renders an empty state with no entries", () => {
    render(<JournalEntries />);
    expect(screen.getByText("No journal entries")).toBeInTheDocument();
  });
});
