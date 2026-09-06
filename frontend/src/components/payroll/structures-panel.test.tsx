import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SalaryStructure } from "@/lib/payroll/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

vi.mock("next/link", () => ({ default: ({ children }: { children: React.ReactNode }) => <a>{children}</a> }));

const structuresQ = { isLoading: false, isError: false, data: [] as SalaryStructure[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
let canManage = true;

vi.mock("@/lib/payroll/hooks", () => ({
  useStructures: () => structuresQ,
  useCreateStructure: () => create,
  useCanManagePayroll: () => canManage,
}));

import { StructuresPanel } from "./structures-panel";

const st = (over: Partial<SalaryStructure> = {}): SalaryStructure => ({
  id: "s1", name: "Standard monthly", currency: "USD", country: "US",
  effective_date: "2026-01-01", status: "active", ...over,
});

beforeEach(() => {
  structuresQ.data = [];
  canManage = true;
  vi.clearAllMocks();
});

describe("StructuresPanel", () => {
  it("lists structures with status", () => {
    structuresQ.data = [st()];
    render(<StructuresPanel />);
    expect(screen.getByText("Standard monthly")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("creates a structure", async () => {
    render(<StructuresPanel />);
    fireEvent.click(screen.getAllByRole("button", { name: "New structure" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Exec plan" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Exec plan", currency: "USD", country: "US" }),
      ),
    );
  });

  it("hides create for non-admins", () => {
    canManage = false;
    render(<StructuresPanel />);
    expect(screen.queryByRole("button", { name: "New structure" })).not.toBeInTheDocument();
  });
});
