import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ProductionOrder } from "@/lib/manufacturing/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

// Stub the lifecycle so this test focuses on list + create.
vi.mock("./order-lifecycle", () => ({ OrderLifecycle: ({ orderId }: { orderId: string }) => <div>lifecycle:{orderId}</div> }));

const ordersQ = { isLoading: false, isError: false, data: [] as ProductionOrder[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({ id: "o9" })), isPending: false };
let canManage = true;

vi.mock("@/lib/manufacturing/hooks", () => ({
  useOrders: () => ordersQ,
  useCreateOrder: () => create,
  useCanManageManufacturing: () => canManage,
}));

import { OrdersPanel } from "./orders-panel";

const order = (over: Partial<ProductionOrder> = {}): ProductionOrder => ({
  id: "o1", number: "MO-0001", product_item_id: "prod-1", quantity: "10", status: "draft",
  material_cost: "0", labor_cost: "0", overhead_cost: "0", total_cost: "0", good_qty: "0", ...over,
});

beforeEach(() => {
  ordersQ.data = [];
  canManage = true;
  vi.clearAllMocks();
});

describe("OrdersPanel", () => {
  it("lists orders with status", () => {
    ordersQ.data = [order({ status: "released" })];
    render(<OrdersPanel />);
    expect(screen.getByText("MO-0001")).toBeInTheDocument();
    expect(screen.getByText("released")).toBeInTheDocument();
  });

  it("creates an order and selects it", async () => {
    render(<OrdersPanel />);
    fireEvent.click(screen.getAllByRole("button", { name: "New order" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Product item id"), { target: { value: "prod-9" } });
    fireEvent.change(within(dialog).getByLabelText("Quantity"), { target: { value: "25" } });
    fireEvent.change(within(dialog).getByLabelText("BOM id"), { target: { value: "bom-1" } });
    fireEvent.change(within(dialog).getByLabelText("Routing id"), { target: { value: "rt-1" } });
    fireEvent.change(within(dialog).getByLabelText("Warehouse id"), { target: { value: "wh-1" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith({
        product_item_id: "prod-9", quantity: "25", bom_id: "bom-1", routing_id: "rt-1", warehouse_id: "wh-1",
      }),
    );
    // The newly created order id drives the lifecycle pane.
    await waitFor(() => expect(screen.getByText("lifecycle:o9")).toBeInTheDocument());
  });

  it("selecting an order shows its lifecycle", () => {
    ordersQ.data = [order()];
    render(<OrdersPanel />);
    fireEvent.click(screen.getByText("MO-0001"));
    expect(screen.getByText("lifecycle:o1")).toBeInTheDocument();
  });

  it("hides create for non-admins", () => {
    canManage = false;
    render(<OrdersPanel />);
    expect(screen.queryByRole("button", { name: "New order" })).not.toBeInTheDocument();
  });
});
