import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import type { PayrollRun, RunStatus } from "@/lib/payroll/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const runQ = { isLoading: false, isError: false, data: undefined as PayrollRun | undefined };
const summaryQ = { isLoading: false, isError: false, data: undefined as Record<string, unknown> | undefined };
const registerQ = { isLoading: false, isError: false, data: { rows: [] as Record<string, string>[] } };
const calculate = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const approve = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const post = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const lock = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
let canManage = true;

vi.mock("@/lib/payroll/hooks", () => ({
  useRun: () => runQ,
  useRunSummary: () => summaryQ,
  useRunRegister: () => registerQ,
  useCalculateRun: () => calculate,
  useApproveRun: () => approve,
  usePostRun: () => post,
  useLockRun: () => lock,
  useCanManagePayroll: () => canManage,
}));

import { RunLifecycle } from "./run-lifecycle";

const run = (status: RunStatus): PayrollRun => ({
  id: "r1", payroll_period_id: "p1", status, total_gross: "5000", total_deductions: "1000",
  total_net: "4000", employee_count: 3, journal_entry_id: null,
});

function btn(name: string) {
  return screen.getByRole("button", { name }) as HTMLButtonElement;
}

beforeEach(() => {
  runQ.data = run("draft");
  summaryQ.data = undefined;
  registerQ.data = { rows: [] };
  canManage = true;
  vi.clearAllMocks();
});

describe("RunLifecycle", () => {
  it("enables only Calculate in draft", () => {
    runQ.data = run("draft");
    render(<RunLifecycle runId="r1" />);
    expect(btn("Calculate").disabled).toBe(false);
    expect(btn("Approve").disabled).toBe(true);
    expect(btn("Post").disabled).toBe(true);
    expect(btn("Lock").disabled).toBe(true);
  });

  it("enables only Approve when completed", () => {
    runQ.data = run("completed");
    render(<RunLifecycle runId="r1" />);
    expect(btn("Calculate").disabled).toBe(true);
    expect(btn("Approve").disabled).toBe(false);
    expect(btn("Post").disabled).toBe(true);
  });

  it("enables only Post when approved", () => {
    runQ.data = run("approved");
    render(<RunLifecycle runId="r1" />);
    expect(btn("Approve").disabled).toBe(true);
    expect(btn("Post").disabled).toBe(false);
    expect(btn("Lock").disabled).toBe(true);
  });

  it("enables only Lock when posted", () => {
    runQ.data = run("posted");
    render(<RunLifecycle runId="r1" />);
    expect(btn("Post").disabled).toBe(true);
    expect(btn("Lock").disabled).toBe(false);
  });

  it("calculates the run", async () => {
    runQ.data = run("draft");
    render(<RunLifecycle runId="r1" />);
    fireEvent.click(btn("Calculate"));
    await waitFor(() => expect(calculate.mutateAsync).toHaveBeenCalledWith("r1"));
  });

  it("approves the run", async () => {
    runQ.data = run("completed");
    render(<RunLifecycle runId="r1" />);
    fireEvent.click(btn("Approve"));
    await waitFor(() => expect(approve.mutateAsync).toHaveBeenCalledWith("r1"));
  });

  it("posts the run", async () => {
    runQ.data = run("approved");
    render(<RunLifecycle runId="r1" />);
    fireEvent.click(btn("Post"));
    await waitFor(() => expect(post.mutateAsync).toHaveBeenCalledWith("r1"));
  });

  it("surfaces a segregation-of-duties error from approve", async () => {
    runQ.data = run("completed");
    approve.mutateAsync.mockRejectedValueOnce(
      new ApiError({ status: 400, message: "Run creator cannot approve their own run" }),
    );
    render(<RunLifecycle runId="r1" />);
    fireEvent.click(btn("Approve"));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Run creator cannot approve their own run"),
    );
  });

  it("renders the payslip register rows", () => {
    runQ.data = run("posted");
    registerQ.data = { rows: [{ payslip_id: "ps1", employee_record_id: "abcdef12", total_gross: "5000", total_deductions: "1000", total_net: "4000" }] };
    render(<RunLifecycle runId="r1" />);
    // The truncated employee id is unique to the register table.
    expect(screen.getByText("abcdef12")).toBeInTheDocument();
  });

  it("hides lifecycle buttons for non-admins", () => {
    canManage = false;
    render(<RunLifecycle runId="r1" />);
    expect(screen.queryByRole("button", { name: "Calculate" })).not.toBeInTheDocument();
  });
});
