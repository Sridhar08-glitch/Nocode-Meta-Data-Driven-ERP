import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AccountingPeriod } from "@/lib/ledger/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const periodsQ = { isLoading: false, isError: false, data: [] as AccountingPeriod[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const close = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const reopen = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const genYear = { mutateAsync: vi.fn(() => Promise.resolve({ created: 12, skipped: 0, fiscal_year: "FY2026" })), isPending: false };

vi.mock("@/lib/ledger/hooks", () => ({
  usePeriods: () => periodsQ,
  useCreatePeriod: () => create,
  useClosePeriod: () => close,
  useReopenPeriod: () => reopen,
  useGenerateFiscalYear: () => genYear,
}));

import { AccountingPeriods } from "./accounting-periods";

const period = (over: Partial<AccountingPeriod> = {}): AccountingPeriod => ({
  id: "p1", code: "2026-06", name: "", start_date: "2026-06-01", end_date: "2026-06-30",
  status: "open", fiscal_year: "", closed_at: null, closed_by: null, ...over,
});

beforeEach(() => {
  periodsQ.data = [];
  for (const m of [create, close, reopen, genYear]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("AccountingPeriods", () => {
  it("closes a period (soft)", async () => {
    periodsQ.data = [period()];
    render(<AccountingPeriods />);
    fireEvent.click(screen.getByRole("button", { name: "Close 2026-06" }));
    await waitFor(() => expect(close.mutateAsync).toHaveBeenCalledWith({ id: "p1" }));
  });

  it("locks a period", async () => {
    periodsQ.data = [period()];
    render(<AccountingPeriods />);
    fireEvent.click(screen.getByRole("button", { name: "Lock 2026-06" }));
    await waitFor(() => expect(close.mutateAsync).toHaveBeenCalledWith({ id: "p1", lock: true }));
  });

  it("reopens a closed period and offers no actions on a locked one", () => {
    periodsQ.data = [period({ status: "locked" })];
    const { rerender } = render(<AccountingPeriods />);
    expect(screen.queryByRole("button", { name: /Reopen/ })).not.toBeInTheDocument();
    periodsQ.data = [period({ status: "closed" })];
    rerender(<AccountingPeriods />);
    expect(screen.getByRole("button", { name: "Reopen 2026-06" })).toBeInTheDocument();
  });

  it("generates the current fiscal year", async () => {
    render(<AccountingPeriods />);
    const year = new Date().getFullYear();
    fireEvent.click(screen.getByRole("button", { name: `Generate ${year}` }));
    await waitFor(() => expect(genYear.mutateAsync).toHaveBeenCalledWith({ year }));
  });

  it("creates a period with code and dates", async () => {
    render(<AccountingPeriods />);
    fireEvent.click(screen.getAllByRole("button", { name: "New period" })[0]);
    fireEvent.change(screen.getByLabelText("Code"), { target: { value: "2026-07" } });
    fireEvent.change(screen.getByLabelText("Start"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByLabelText("End"), { target: { value: "2026-07-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ code: "2026-07", start_date: "2026-07-01", end_date: "2026-07-31" }),
      ),
    );
  });
});
