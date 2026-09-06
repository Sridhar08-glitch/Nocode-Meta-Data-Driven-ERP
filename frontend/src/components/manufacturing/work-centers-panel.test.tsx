import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WorkCenter } from "@/lib/manufacturing/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const centersQ = { isLoading: false, isError: false, data: [] as WorkCenter[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
let canManage = true;

vi.mock("@/lib/manufacturing/hooks", () => ({
  useWorkCenters: () => centersQ,
  useCreateWorkCenter: () => create,
  useCanManageManufacturing: () => canManage,
}));

import { WorkCentersPanel } from "./work-centers-panel";

const wc = (over: Partial<WorkCenter> = {}): WorkCenter => ({
  id: "w1", code: "WC-01", name: "Assembly", center_type: "labor",
  capacity_per_hour: "10", efficiency: "1", cost_per_hour: "25", is_active: true, ...over,
});

beforeEach(() => {
  centersQ.data = [];
  canManage = true;
  vi.clearAllMocks();
});

describe("WorkCentersPanel", () => {
  it("lists work centers", () => {
    centersQ.data = [wc()];
    render(<WorkCentersPanel />);
    expect(screen.getByText("WC-01")).toBeInTheDocument();
    expect(screen.getByText("Assembly")).toBeInTheDocument();
  });

  it("creates a work center", async () => {
    render(<WorkCentersPanel />);
    fireEvent.click(screen.getAllByRole("button", { name: "New work center" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Code"), { target: { value: "WC-02" } });
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "CNC mill" } });
    fireEvent.change(within(dialog).getByLabelText("Cost/hr"), { target: { value: "40" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          code: "WC-02", name: "CNC mill", center_type: "labor", cost_per_hour: "40",
        }),
      ),
    );
  });

  it("hides create for non-admins", () => {
    canManage = false;
    render(<WorkCentersPanel />);
    expect(screen.queryByRole("button", { name: "New work center" })).not.toBeInTheDocument();
  });
});
