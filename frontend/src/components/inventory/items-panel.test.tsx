import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Item } from "@/lib/inventory/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const itemsQ = { isLoading: false, isError: false, data: [] as Item[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };

vi.mock("@/lib/inventory/hooks", () => ({
  useItems: () => itemsQ,
  useCreateItem: () => create,
  useDeleteItem: () => del,
}));

import { ItemsPanel } from "./items-panel";

const item = (over: Partial<Item> = {}): Item => ({
  id: "i1", sku: "WIDGET-01", name: "Blue widget", category: null, uom: "ea",
  valuation_method: "average", standard_cost: "0", track_inventory: true, is_active: true,
  inventory_account_code: "", cogs_account_code: "", description: "", created_at: "", updated_at: "", ...over,
});

beforeEach(() => {
  itemsQ.data = [];
  for (const m of [create, del]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("ItemsPanel", () => {
  it("lists items with sku and valuation method", () => {
    itemsQ.data = [item()];
    render(<ItemsPanel />);
    expect(screen.getByText("WIDGET-01")).toBeInTheDocument();
    expect(screen.getByText("Blue widget")).toBeInTheDocument();
    expect(screen.getByText("average")).toBeInTheDocument();
  });

  it("creates an item with sku, name and valuation", async () => {
    render(<ItemsPanel />);
    fireEvent.click(screen.getAllByRole("button", { name: "New item" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("SKU"), { target: { value: "BOLT-9" } });
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Hex bolt" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ sku: "BOLT-9", name: "Hex bolt", valuation_method: "average" }),
      ),
    );
  });

  it("deletes an item", async () => {
    itemsQ.data = [item()];
    render(<ItemsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Delete WIDGET-01" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("i1"));
  });
});
