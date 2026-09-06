import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BalanceSheet, ProfitLoss, TrialBalance } from "@/lib/ledger/api";

const tb: { isLoading: boolean; data: TrialBalance | undefined } = { isLoading: false, data: undefined };
const pl: { isLoading: boolean; data: ProfitLoss | undefined } = { isLoading: false, data: undefined };
const bs: { isLoading: boolean; data: BalanceSheet | undefined } = { isLoading: false, data: undefined };

vi.mock("@/lib/ledger/hooks", () => ({
  useTrialBalance: () => tb,
  useProfitLoss: () => pl,
  useBalanceSheet: () => bs,
  useGeneralLedger: () => ({ isLoading: false, data: undefined }),
  useLedgerAccounts: () => ({ data: [] }),
}));

import { FinancialReports } from "./financial-reports";

beforeEach(() => {
  tb.data = {
    as_of: null,
    rows: [
      { account_id: "a1", code: "1000", name: "Cash", account_type: "asset", debit: "200.00", credit: "0.00" },
      { account_id: "a2", code: "4000", name: "Sales", account_type: "revenue", debit: "0.00", credit: "300.00" },
    ],
    total_debit: "300.00", total_credit: "300.00", balanced: true,
  };
  pl.data = {
    date_from: null, date_to: null,
    revenue: [{ code: "4000", name: "Sales", amount: "300.00" }],
    expense: [{ code: "6100", name: "Rent", amount: "100.00" }],
    total_revenue: "300.00", total_expense: "100.00", net_income: "200.00",
  };
  bs.data = {
    as_of: null, assets: [{ code: "1000", name: "Cash", amount: "200.00" }],
    liabilities: [], equity: [{ code: "—", name: "Current earnings", amount: "200.00" }],
    total_assets: "200.00", total_liabilities: "0.00", total_equity: "200.00",
    total_liabilities_equity: "200.00", balanced: true,
  };
  vi.clearAllMocks();
});

describe("FinancialReports", () => {
  it("renders the trial balance with totals and a balanced badge by default", () => {
    render(<FinancialReports />);
    expect(screen.getByText("Cash")).toBeInTheDocument();
    expect(screen.getByText("Balanced")).toBeInTheDocument();
    // total row
    expect(screen.getAllByText("300.00").length).toBeGreaterThan(0);
  });

  it("switches to the balance sheet and shows the A=L+E check", async () => {
    render(<FinancialReports />);
    fireEvent.click(screen.getByRole("combobox", { name: "Report" }));
    const option = await screen.findByRole("option", { name: "Balance Sheet" });
    fireEvent.click(option);
    expect(screen.getByText("Balanced (A = L + E)")).toBeInTheDocument();
    expect(screen.getByText(/Liabilities \+ Equity/)).toBeInTheDocument();
  });

  it("switches to P&L and shows net income", async () => {
    render(<FinancialReports />);
    fireEvent.click(screen.getByRole("combobox", { name: "Report" }));
    fireEvent.click(await screen.findByRole("option", { name: "Profit & Loss" }));
    const net = screen.getByText("Net income").closest("div");
    expect(net && within(net).getByText("200.00")).toBeTruthy();
  });
});
