import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Adjustment, Advance, Loan, Overtime } from "@/lib/payroll/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const loansQ = { isLoading: false, isError: false, data: [] as Loan[] };
const advancesQ = { isLoading: false, isError: false, data: [] as Advance[] };
const overtimeQ = { isLoading: false, isError: false, data: [] as Overtime[] };
const adjustmentsQ = { isLoading: false, isError: false, data: [] as Adjustment[] };
const createLoan = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const createAdvance = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const createOvertime = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approveOvertime = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const createAdjustment = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };

vi.mock("@/lib/payroll/hooks", () => ({
  useLoans: () => loansQ,
  useAdvances: () => advancesQ,
  useOvertime: () => overtimeQ,
  useAdjustments: () => adjustmentsQ,
  useCreateLoan: () => createLoan,
  useCreateAdvance: () => createAdvance,
  useCreateOvertime: () => createOvertime,
  useApproveOvertime: () => approveOvertime,
  useCreateAdjustment: () => createAdjustment,
}));

import { InputsPanel } from "./inputs-panel";

beforeEach(() => {
  loansQ.data = [];
  advancesQ.data = [];
  overtimeQ.data = [];
  adjustmentsQ.data = [];
  vi.clearAllMocks();
});

describe("InputsPanel", () => {
  it("creates a loan with employee, amount and installment", async () => {
    render(<InputsPanel />);
    fireEvent.change(screen.getByLabelText("Employee record id"), { target: { value: "emp-1" } });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "1200" } });
    fireEvent.change(screen.getByLabelText("Installment"), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Create loan" }));
    await waitFor(() =>
      expect(createLoan.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ employee_record_id: "emp-1", amount: "1200", installment: "100" }),
      ),
    );
  });

  it("validates required loan fields", async () => {
    render(<InputsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Create loan" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Employee and amount are required"));
    expect(createLoan.mutateAsync).not.toHaveBeenCalled();
  });

  it("logs overtime after switching tabs", async () => {
    render(<InputsPanel />);
    fireEvent.click(screen.getByRole("tab", { name: "Overtime" }));
    fireEvent.change(screen.getByLabelText("Employee record id"), { target: { value: "emp-2" } });
    fireEvent.change(screen.getByLabelText("Hours"), { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Log overtime" }));
    await waitFor(() =>
      expect(createOvertime.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ employee_record_id: "emp-2", hours: "8", multiplier: "1.5" }),
      ),
    );
  });

  it("approves overtime", async () => {
    overtimeQ.data = [{ id: "ot1", employee_record_id: "emp-2", hours: "8", rate: "10", multiplier: "1.5", status: "pending" }];
    render(<InputsPanel />);
    fireEvent.click(screen.getByRole("tab", { name: "Overtime" }));
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(approveOvertime.mutateAsync).toHaveBeenCalledWith("ot1"));
  });

  it("creates an adjustment with adj_type", async () => {
    render(<InputsPanel />);
    fireEvent.click(screen.getByRole("tab", { name: "Adjustments" }));
    fireEvent.change(screen.getByLabelText("Employee record id"), { target: { value: "emp-3" } });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("Name / memo"), { target: { value: "Bonus" } });
    fireEvent.click(screen.getByRole("button", { name: "Create adjustment" }));
    await waitFor(() =>
      expect(createAdjustment.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ employee_record_id: "emp-3", adj_type: "bonus", amount: "500", name: "Bonus" }),
      ),
    );
  });
});
