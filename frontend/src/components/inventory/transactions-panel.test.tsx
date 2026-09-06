import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Item, Warehouse } from "@/lib/inventory/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const itemsQ = { isLoading: false, isError: false, data: [] as Item[] };
const whQ = { isLoading: false, isError: false, data: [] as Warehouse[] };
const receive = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const issue = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const adjust = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const transfer = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };

vi.mock("@/lib/inventory/hooks", () => ({
  useItems: () => itemsQ,
  useWarehouses: () => whQ,
  useReceive: () => receive,
  useIssue: () => issue,
  useAdjust: () => adjust,
  useTransfer: () => transfer,
}));

import { TransactionsPanel } from "./transactions-panel";

const item = (over: Partial<Item> = {}): Item => ({
  id: "i1", sku: "WIDGET-01", name: "Blue widget", category: null, uom: "ea",
  valuation_method: "average", standard_cost: "0", track_inventory: true, is_active: true,
  inventory_account_code: "", cogs_account_code: "", description: "", created_at: "", updated_at: "", ...over,
});
const wh = (over: Partial<Warehouse> = {}): Warehouse => ({
  id: "w1", code: "MAIN", name: "Main warehouse", is_active: true, created_at: "", updated_at: "", ...over,
});

beforeEach(() => {
  itemsQ.data = [item()];
  whQ.data = [wh(), wh({ id: "w2", code: "WEST", name: "West depot" })];
  for (const m of [receive, issue, adjust, transfer]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("TransactionsPanel", () => {
  it("prompts to set up master data when none exists", () => {
    itemsQ.data = [];
    render(<TransactionsPanel />);
    expect(screen.getByText("Set up master data first")).toBeInTheDocument();
  });

  it("posts a receive with item, warehouse, quantity and unit cost", async () => {
    render(<TransactionsPanel />);
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Unit cost"), { target: { value: "2.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Post receive" }));
    await waitFor(() =>
      expect(receive.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ item: "i1", warehouse: "w1", quantity: "10", unit_cost: "2.5" }),
      ),
    );
  });

  it("posts an issue after switching tabs", async () => {
    render(<TransactionsPanel />);
    fireEvent.click(screen.getByRole("tab", { name: "Issue" }));
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Post issue" }));
    await waitFor(() =>
      expect(issue.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ item: "i1", warehouse: "w1", quantity: "3" }),
      ),
    );
  });

  it("rejects a transfer when source and destination match", async () => {
    whQ.data = [wh()]; // only one warehouse → from == to
    render(<TransactionsPanel />);
    fireEvent.click(screen.getByRole("tab", { name: "Transfer" }));
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Post transfer" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Source and destination warehouses must differ"));
    expect(transfer.mutateAsync).not.toHaveBeenCalled();
  });

  it("validates required quantity", async () => {
    render(<TransactionsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Post receive" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Item, warehouse and quantity are required"));
    expect(receive.mutateAsync).not.toHaveBeenCalled();
  });
});
