import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import type { Operation, OrderStatus, ProductionOrder, Reservation } from "@/lib/manufacturing/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const ordersQ = { isLoading: false, isError: false, data: [] as ProductionOrder[] };
const reservationsQ = { isLoading: false, isError: false, data: [] as Reservation[] };
const operationsQ = { isLoading: false, isError: false, data: [] as Operation[] };
const oeeQ = { isLoading: false, isError: false, data: undefined as Record<string, string> | undefined };
const release = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const issue = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const close = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const complete = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const completeOp = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
let canManage = true;

vi.mock("@/lib/manufacturing/hooks", () => ({
  useOrders: () => ordersQ,
  useReservations: () => reservationsQ,
  useOperations: () => operationsQ,
  useOrderOee: () => oeeQ,
  useReleaseOrder: () => release,
  useIssueOrder: () => issue,
  useCloseOrder: () => close,
  useCompleteOrder: () => complete,
  useCompleteOperation: () => completeOp,
  useCanManageManufacturing: () => canManage,
}));

import { OrderLifecycle } from "./order-lifecycle";

const order = (status: OrderStatus): ProductionOrder => ({
  id: "o1", number: "MO-0001", product_item_id: "prod-1", quantity: "10", status,
  material_cost: "100", labor_cost: "20", overhead_cost: "5", total_cost: "125", good_qty: "0",
});

function btn(name: string) {
  return screen.getByRole("button", { name }) as HTMLButtonElement;
}

beforeEach(() => {
  ordersQ.data = [order("draft")];
  reservationsQ.data = [];
  operationsQ.data = [];
  oeeQ.data = undefined;
  canManage = true;
  vi.clearAllMocks();
});

describe("OrderLifecycle", () => {
  it("enables only Release in draft", () => {
    ordersQ.data = [order("draft")];
    render(<OrderLifecycle orderId="o1" />);
    expect(btn("Release").disabled).toBe(false);
    expect(btn("Issue").disabled).toBe(true);
    expect(btn("Complete").disabled).toBe(true);
    expect(btn("Close").disabled).toBe(true);
  });

  it("enables Release in planned", () => {
    ordersQ.data = [order("planned")];
    render(<OrderLifecycle orderId="o1" />);
    expect(btn("Release").disabled).toBe(false);
  });

  it("enables only Issue and Complete when released", () => {
    ordersQ.data = [order("released")];
    render(<OrderLifecycle orderId="o1" />);
    expect(btn("Release").disabled).toBe(true);
    expect(btn("Issue").disabled).toBe(false);
    expect(btn("Complete").disabled).toBe(false);
    expect(btn("Close").disabled).toBe(true);
  });

  it("enables Complete when in_progress (and not Issue)", () => {
    ordersQ.data = [order("in_progress")];
    render(<OrderLifecycle orderId="o1" />);
    expect(btn("Issue").disabled).toBe(true);
    expect(btn("Complete").disabled).toBe(false);
  });

  it("enables only Close when completed", () => {
    ordersQ.data = [order("completed")];
    render(<OrderLifecycle orderId="o1" />);
    expect(btn("Complete").disabled).toBe(true);
    expect(btn("Close").disabled).toBe(false);
  });

  it("releases the order", async () => {
    ordersQ.data = [order("draft")];
    render(<OrderLifecycle orderId="o1" />);
    fireEvent.click(btn("Release"));
    await waitFor(() => expect(release.mutateAsync).toHaveBeenCalledWith("o1"));
  });

  it("issues the order", async () => {
    ordersQ.data = [order("released")];
    render(<OrderLifecycle orderId="o1" />);
    fireEvent.click(btn("Issue"));
    await waitFor(() => expect(issue.mutateAsync).toHaveBeenCalledWith("o1"));
  });

  it("completes the order with good_qty + overhead + lot", async () => {
    ordersQ.data = [order("released")];
    render(<OrderLifecycle orderId="o1" />);
    fireEvent.click(btn("Complete"));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Good quantity"), { target: { value: "9" } });
    fireEvent.change(within(dialog).getByLabelText("Overhead %"), { target: { value: "10" } });
    fireEvent.change(within(dialog).getByLabelText("Lot number"), { target: { value: "LOT-1" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Complete" }));
    await waitFor(() =>
      expect(complete.mutateAsync).toHaveBeenCalledWith({
        id: "o1", good_qty: "9", overhead_percent: "10", lot_number: "LOT-1",
      }),
    );
  });

  it("closes the order", async () => {
    ordersQ.data = [order("completed")];
    render(<OrderLifecycle orderId="o1" />);
    fireEvent.click(btn("Close"));
    await waitFor(() => expect(close.mutateAsync).toHaveBeenCalledWith("o1"));
  });

  it("surfaces a server error from release", async () => {
    ordersQ.data = [order("draft")];
    release.mutateAsync.mockRejectedValueOnce(
      new ApiError({ status: 400, message: "No active BOM for product" }),
    );
    render(<OrderLifecycle orderId="o1" />);
    fireEvent.click(btn("Release"));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("No active BOM for product"));
  });

  it("renders reservations", () => {
    ordersQ.data = [order("released")];
    reservationsQ.data = [
      { id: "r1", production_order_id: "o1", component_item_id: "comp-abc", quantity: "5", status: "reserved" },
    ];
    render(<OrderLifecycle orderId="o1" />);
    expect(screen.getByText("comp-abc")).toBeInTheDocument();
  });

  it("completes an operation", async () => {
    ordersQ.data = [order("in_progress")];
    operationsQ.data = [
      {
        id: "op1", production_order_id: "o1", work_center_id: "wc1", sequence: 1, name: "Assembly",
        status: "pending", labor_minutes: "0", machine_minutes: "0", downtime_minutes: "0",
        good_qty: "0", reject_qty: "0",
      },
    ];
    render(<OrderLifecycle orderId="o1" />);
    // Both the order-level and the operation-row buttons read "Complete";
    // the operation-row Complete is the last one.
    const completeButtons = screen.getAllByRole("button", { name: "Complete" });
    fireEvent.click(completeButtons[completeButtons.length - 1]);
    // operation-complete dialog
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Labor minutes"), { target: { value: "30" } });
    fireEvent.change(within(dialog).getByLabelText("Good qty"), { target: { value: "8" } });
    fireEvent.change(within(dialog).getByLabelText("Reject qty"), { target: { value: "2" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Complete operation" }));
    await waitFor(() =>
      expect(completeOp.mutateAsync).toHaveBeenCalledWith({
        id: "op1", labor_minutes: "30", machine_minutes: "0", downtime_minutes: "0",
        good_qty: "8", reject_qty: "2",
      }),
    );
  });

  it("shows OEE when completed", () => {
    ordersQ.data = [order("completed")];
    oeeQ.data = { availability: "0.9", performance: "0.8", quality: "0.95", oee: "0.68" };
    render(<OrderLifecycle orderId="o1" />);
    expect(screen.getByText(/Overall equipment effectiveness/)).toBeInTheDocument();
    expect(screen.getByText("0.68")).toBeInTheDocument();
  });

  it("hides lifecycle buttons for non-admins", () => {
    canManage = false;
    ordersQ.data = [order("draft")];
    render(<OrderLifecycle orderId="o1" />);
    expect(screen.queryByRole("button", { name: "Release" })).not.toBeInTheDocument();
  });
});
