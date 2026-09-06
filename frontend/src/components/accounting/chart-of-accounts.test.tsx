import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LedgerAccount } from "@/lib/ledger/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const accountsQ = { isLoading: false, isError: false, data: [] as LedgerAccount[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const seed = { mutateAsync: vi.fn(() => Promise.resolve({ created: 24, skipped: 0 })), isPending: false };

vi.mock("@/lib/ledger/hooks", () => ({
  useLedgerAccounts: () => accountsQ,
  useCreateAccount: () => create,
  useDeleteAccount: () => del,
  useSeedChart: () => seed,
}));

import { ChartOfAccounts } from "./chart-of-accounts";

const acct = (over: Partial<LedgerAccount> = {}): LedgerAccount => ({
  id: "a1", code: "1000", name: "Cash", account_type: "asset", parent: null, is_group: false,
  is_active: true, currency: "", description: "", normal_balance: "debit", created_at: "", updated_at: "", ...over,
});

beforeEach(() => {
  accountsQ.data = [];
  for (const m of [create, del, seed]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("ChartOfAccounts", () => {
  it("groups accounts by type", () => {
    accountsQ.data = [acct(), acct({ id: "a2", code: "4000", name: "Sales", account_type: "revenue", normal_balance: "credit" })];
    render(<ChartOfAccounts />);
    expect(screen.getByText("asset")).toBeInTheDocument();
    expect(screen.getByText("revenue")).toBeInTheDocument();
    expect(screen.getByText("Cash")).toBeInTheDocument();
  });

  it("creates an account with code/name/type", async () => {
    render(<ChartOfAccounts />);
    fireEvent.click(screen.getAllByRole("button", { name: "New account" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Code"), { target: { value: "1000" } });
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Cash" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ code: "1000", name: "Cash", account_type: "asset" }),
      ),
    );
  });

  it("deletes an account", async () => {
    accountsQ.data = [acct()];
    render(<ChartOfAccounts />);
    fireEvent.click(screen.getByRole("button", { name: "Delete 1000" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("a1"));
  });

  it("seeds the standard chart", async () => {
    render(<ChartOfAccounts />);
    fireEvent.click(screen.getAllByRole("button", { name: "Seed standard chart" })[0]);
    await waitFor(() => expect(seed.mutateAsync).toHaveBeenCalled());
  });
});
