import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Warehouse } from "@/lib/inventory/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const whQ = { isLoading: false, isError: false, data: [] as Warehouse[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };

vi.mock("@/lib/inventory/hooks", () => ({
  useWarehouses: () => whQ,
  useCreateWarehouse: () => create,
  useDeleteWarehouse: () => del,
}));

import { WarehousesPanel } from "./warehouses-panel";

const wh = (over: Partial<Warehouse> = {}): Warehouse => ({
  id: "w1", code: "MAIN", name: "Main warehouse", is_active: true, created_at: "", updated_at: "", ...over,
});

beforeEach(() => {
  whQ.data = [];
  for (const m of [create, del]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("WarehousesPanel", () => {
  it("lists warehouses", () => {
    whQ.data = [wh()];
    render(<WarehousesPanel />);
    expect(screen.getByText("MAIN")).toBeInTheDocument();
    expect(screen.getByText("Main warehouse")).toBeInTheDocument();
  });

  it("creates a warehouse with code and name", async () => {
    render(<WarehousesPanel />);
    fireEvent.click(screen.getAllByRole("button", { name: "New warehouse" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Code"), { target: { value: "WEST" } });
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "West depot" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ code: "WEST", name: "West depot" })),
    );
  });

  it("deletes a warehouse", async () => {
    whQ.data = [wh()];
    render(<WarehousesPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Delete MAIN" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("w1"));
  });
});
