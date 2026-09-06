import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PayPeriod } from "@/lib/payroll/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const periodsQ = { isLoading: false, isError: false, data: [] as PayPeriod[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({ id: "p9", name: "Feb" })), isPending: false };
const open = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const close = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const lock = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const reopen = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
let canManage = true;

vi.mock("@/lib/payroll/hooks", () => ({
  usePeriods: () => periodsQ,
  useCreatePeriod: () => create,
  useOpenPeriod: () => open,
  useClosePeriod: () => close,
  useLockPeriod: () => lock,
  useReopenPeriod: () => reopen,
  useCanManagePayroll: () => canManage,
}));

import { PeriodsPanel } from "./periods-panel";

const period = (over: Partial<PayPeriod> = {}): PayPeriod => ({
  id: "p1", name: "January 2026", start_date: "2026-01-01", end_date: "2026-01-31", status: "draft", ...over,
});

beforeEach(() => {
  periodsQ.data = [];
  canManage = true;
  vi.clearAllMocks();
});

describe("PeriodsPanel", () => {
  it("shows Open for a draft period and opens it", async () => {
    periodsQ.data = [period({ status: "draft" })];
    render(<PeriodsPanel selectedId={null} onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() => expect(open.mutateAsync).toHaveBeenCalledWith("p1"));
  });

  it("shows Close for an open period (not Open/Lock)", () => {
    periodsQ.data = [period({ status: "open" })];
    render(<PeriodsPanel selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Lock" })).not.toBeInTheDocument();
  });

  it("shows Reopen and Lock for a closed period", () => {
    periodsQ.data = [period({ status: "closed" })];
    render(<PeriodsPanel selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Reopen" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Lock" })).toBeInTheDocument();
  });

  it("creates a period", async () => {
    render(<PeriodsPanel selectedId={null} onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "New period" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "February 2026" } });
    fireEvent.change(within(dialog).getByLabelText("Start date"), { target: { value: "2026-02-01" } });
    fireEvent.change(within(dialog).getByLabelText("End date"), { target: { value: "2026-02-28" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ name: "February 2026", start_date: "2026-02-01", end_date: "2026-02-28" }),
      ),
    );
  });

  it("selects a period on click", () => {
    const onSelect = vi.fn();
    periodsQ.data = [period()];
    render(<PeriodsPanel selectedId={null} onSelect={onSelect} />);
    fireEvent.click(screen.getByText("January 2026"));
    expect(onSelect).toHaveBeenCalledWith("p1");
  });

  it("hides lifecycle controls for non-admins", () => {
    canManage = false;
    periodsQ.data = [period({ status: "draft" })];
    render(<PeriodsPanel selectedId={null} onSelect={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Open" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New period" })).not.toBeInTheDocument();
  });
});
