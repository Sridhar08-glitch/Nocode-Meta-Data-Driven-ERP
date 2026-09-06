import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StockBalanceRow, Warehouse } from "@/lib/inventory/api";

const stockQ = { isLoading: false, isError: false, data: { rows: [] as StockBalanceRow[] } };
const valuationQ = { isLoading: false, isError: false, data: { rows: [] as StockBalanceRow[], total_value: "0" } };
const whQ = { isLoading: false, isError: false, data: [] as Warehouse[] };

vi.mock("@/lib/inventory/hooks", () => ({
  useStock: () => stockQ,
  useValuation: () => valuationQ,
  useWarehouses: () => whQ,
}));

import { StockBalance } from "./stock-balance";

const row = (over: Partial<StockBalanceRow> = {}): StockBalanceRow => ({
  item_id: "i1", sku: "WIDGET-01", item_name: "Blue widget", warehouse_id: "w1", warehouse_code: "MAIN",
  on_hand: "10", avg_cost: "2.50", value: "25.00", ...over,
});

beforeEach(() => {
  stockQ.data = { rows: [] };
  valuationQ.data = { rows: [], total_value: "0" };
  whQ.data = [];
});

describe("StockBalance", () => {
  it("shows empty state when no stock", () => {
    render(<StockBalance />);
    expect(screen.getByText("No stock on hand")).toBeInTheDocument();
  });

  it("renders balance rows with on-hand, cost and value", () => {
    stockQ.data = { rows: [row()] };
    valuationQ.data = { rows: [row()], total_value: "25.00" };
    render(<StockBalance />);
    expect(screen.getByText("WIDGET-01")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("2.50")).toBeInTheDocument();
    // total value + row value both render "25.00"
    expect(screen.getAllByText("25.00").length).toBeGreaterThanOrEqual(1);
  });
});
