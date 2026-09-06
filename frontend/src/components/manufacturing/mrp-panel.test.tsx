import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MrpRun } from "@/lib/manufacturing/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const runResult: MrpRun = {
  run_id: "run-1",
  shortages: 1,
  results: [
    { item_id: "item-a", demand: "10", available: "4", net_requirement: "6", suggested_qty: "6", action: "manufacture" },
    { item_id: "item-b", demand: "3", available: "5", net_requirement: "0", suggested_qty: "0", action: "none" },
  ],
};
const runMrp = { mutateAsync: vi.fn(() => Promise.resolve(runResult)), isPending: false };
let canManage = true;

vi.mock("@/lib/manufacturing/hooks", () => ({
  useRunMrp: () => runMrp,
  useCanManageManufacturing: () => canManage,
}));

import { MrpPanel } from "./mrp-panel";

beforeEach(() => {
  canManage = true;
  vi.clearAllMocks();
});

describe("MrpPanel", () => {
  it("runs MRP with the entered demand rows", async () => {
    render(<MrpPanel />);
    fireEvent.change(screen.getByLabelText("Item id"), { target: { value: "item-a" } });
    fireEvent.change(screen.getByLabelText("Demand"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Available"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Run MRP" }));
    await waitFor(() =>
      expect(runMrp.mutateAsync).toHaveBeenCalledWith([{ item_id: "item-a", demand: "10", available: "4" }]),
    );
  });

  it("adds multiple demand rows", async () => {
    render(<MrpPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Add row" }));
    const items = screen.getAllByLabelText("Item id");
    expect(items).toHaveLength(2);
    fireEvent.change(items[0], { target: { value: "item-a" } });
    fireEvent.change(items[1], { target: { value: "item-b" } });
    fireEvent.click(screen.getByRole("button", { name: "Run MRP" }));
    await waitFor(() =>
      expect(runMrp.mutateAsync).toHaveBeenCalledWith([
        { item_id: "item-a", demand: "0", available: "0" },
        { item_id: "item-b", demand: "0", available: "0" },
      ]),
    );
  });

  it("renders the results table with action badges", async () => {
    render(<MrpPanel />);
    fireEvent.change(screen.getByLabelText("Item id"), { target: { value: "item-a" } });
    fireEvent.click(screen.getByRole("button", { name: "Run MRP" }));
    await waitFor(() => expect(screen.getByText("item-a")).toBeInTheDocument());
    expect(screen.getByText("manufacture")).toBeInTheDocument();
    expect(screen.getByText("none")).toBeInTheDocument();
  });

  it("hides Run MRP for non-admins", () => {
    canManage = false;
    render(<MrpPanel />);
    expect(screen.queryByRole("button", { name: "Run MRP" })).not.toBeInTheDocument();
  });
});
