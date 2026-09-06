import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SalaryComponent, SalaryStructure } from "@/lib/payroll/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const structureQ = { isLoading: false, isError: false, data: undefined as SalaryStructure | undefined };
const componentsQ = { isLoading: false, isError: false, data: [] as SalaryComponent[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
let canManage = true;

vi.mock("@/lib/payroll/hooks", () => ({
  useStructure: () => structureQ,
  useComponents: () => componentsQ,
  useCreateComponent: () => create,
  useCanManagePayroll: () => canManage,
}));

import { StructureDetail } from "./structure-detail";

const st: SalaryStructure = {
  id: "s1", name: "Standard", currency: "USD", country: "US", effective_date: "2026-01-01", status: "active",
};
const cmp = (over: Partial<SalaryComponent> = {}): SalaryComponent => ({
  id: "c1", salary_structure_id: "s1", code: "BASIC", name: "Basic salary", component_type: "earning",
  calc_type: "fixed", amount: "1000", formula: "", base_code: "", formula_version: 1, taxable: true,
  gl_account_code: "", sequence: 1, ...over,
});

beforeEach(() => {
  structureQ.data = st;
  componentsQ.data = [];
  canManage = true;
  vi.clearAllMocks();
});

describe("StructureDetail", () => {
  it("lists components sorted by sequence", () => {
    componentsQ.data = [cmp({ id: "c2", code: "TAX", sequence: 2 }), cmp()];
    render(<StructureDetail structureId="s1" />);
    expect(screen.getByText("BASIC")).toBeInTheDocument();
    expect(screen.getByText("TAX")).toBeInTheDocument();
  });

  it("adds a fixed component with sequence and salary_structure_id", async () => {
    render(<StructureDetail structureId="s1" />);
    fireEvent.click(screen.getByRole("button", { name: "Add component" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Code"), { target: { value: "HRA" } });
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "House allowance" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          salary_structure_id: "s1", code: "HRA", name: "House allowance",
          component_type: "earning", calc_type: "fixed", sequence: 1,
        }),
      ),
    );
  });

  it("hides add for non-admins", () => {
    canManage = false;
    render(<StructureDetail structureId="s1" />);
    expect(screen.queryByRole("button", { name: "Add component" })).not.toBeInTheDocument();
  });
});
