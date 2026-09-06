import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PayrollSettings } from "@/lib/payroll/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const settingsQ = { isLoading: false, isError: false, data: undefined as PayrollSettings | undefined };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const setup = { mutateAsync: vi.fn(() => Promise.resolve({ detail: "ok" })), isPending: false };
let canManage = true;

vi.mock("@/lib/payroll/hooks", () => ({
  useSettings: () => settingsQ,
  useUpdateSettings: () => update,
  useRunSetup: () => setup,
  useCanManagePayroll: () => canManage,
}));

import { PayrollOverview } from "./payroll-overview";

const settings = (over: Partial<PayrollSettings> = {}): PayrollSettings => ({
  frequency: "monthly", currency: "USD", default_country: "US", default_cost_center: "",
  pay_start_day: 1, pay_end_day: 28, ...over,
});

beforeEach(() => {
  settingsQ.data = settings();
  canManage = true;
  vi.clearAllMocks();
});

describe("PayrollOverview", () => {
  it("shows settings summary", () => {
    render(<PayrollOverview />);
    expect(screen.getByText("monthly")).toBeInTheDocument();
    expect(screen.getByText("USD")).toBeInTheDocument();
  });

  it("runs setup for admins", async () => {
    render(<PayrollOverview />);
    fireEvent.click(screen.getByRole("button", { name: "Run setup" }));
    await waitFor(() => expect(setup.mutateAsync).toHaveBeenCalled());
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("ok"));
  });

  it("hides write actions for non-admins", () => {
    canManage = false;
    render(<PayrollOverview />);
    expect(screen.queryByRole("button", { name: "Run setup" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit settings" })).not.toBeInTheDocument();
  });

  it("patches settings", async () => {
    render(<PayrollOverview />);
    fireEvent.click(screen.getByRole("button", { name: "Edit settings" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Currency"), { target: { value: "EUR" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(update.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ currency: "EUR", frequency: "monthly", pay_start_day: 1 }),
      ),
    );
  });
});
