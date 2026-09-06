import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Payslip } from "@/lib/payroll/api";

const listQ = { isLoading: false, isError: false, data: [] as Payslip[] };
const detailQ = { isLoading: false, isError: false, data: undefined as Payslip | undefined };
const listSpy = vi.fn();

vi.mock("@/lib/payroll/hooks", () => ({
  usePayslips: (params?: { payroll_run_id?: string }) => {
    listSpy(params);
    return listQ;
  },
  usePayslip: () => detailQ,
}));

import { PayslipsPanel } from "./payslips-panel";

const slip = (over: Partial<Payslip> = {}): Payslip => ({
  id: "ps1", payroll_run_id: "r1", employee_record_id: "abcdef12", total_gross: "5000",
  total_deductions: "1000", total_net: "4000", status: "posted", ...over,
});

beforeEach(() => {
  listQ.data = [];
  detailQ.data = undefined;
  vi.clearAllMocks();
});

describe("PayslipsPanel", () => {
  it("lists payslips with net pay", () => {
    listQ.data = [slip()];
    render(<PayslipsPanel />);
    expect(screen.getByText("4000")).toBeInTheDocument();
  });

  it("filters the list by run id", async () => {
    render(<PayslipsPanel />);
    fireEvent.change(screen.getByLabelText("Filter by run id"), { target: { value: "run-9" } });
    await waitFor(() => expect(listSpy).toHaveBeenLastCalledWith({ payroll_run_id: "run-9" }));
  });

  it("opens a payslip detail with line breakdown", async () => {
    listQ.data = [slip()];
    detailQ.data = slip({
      lines: [
        { code: "BASIC", name: "Basic", component_type: "earning", amount: "5000", source: "structure", sequence: 1 },
        { code: "TAX", name: "Tax", component_type: "deduction", amount: "1000", source: "tax", sequence: 2 },
      ],
    });
    render(<PayslipsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "View" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("BASIC");
    expect(dialog).toHaveTextContent("TAX");
  });
});
