import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Item, StockMovement } from "@/lib/inventory/api";

const itemsQ = { isLoading: false, isError: false, data: [] as Item[] };
const movementsQ = { isLoading: false, isError: false, data: { rows: [] as StockMovement[] } };

vi.mock("@/lib/inventory/hooks", () => ({
  useItems: () => itemsQ,
  useMovements: () => movementsQ,
}));

import { MovementHistory } from "./movement-history";

const mv = (over: Partial<StockMovement> = {}): StockMovement => ({
  id: "m1", item: "i1", sku: "WIDGET-01", warehouse: "w1", warehouse_code: "MAIN", location: null,
  movement_type: "receipt", quantity: "10", unit_cost: "2.50", total_cost: "25.00", on_hand_after: "10",
  occurred_at: "2026-06-23T10:00:00Z", reference: "PO-1001", memo: "", journal_entry_id: null, created_at: "", ...over,
});

beforeEach(() => {
  itemsQ.data = [];
  movementsQ.data = { rows: [] };
});

describe("MovementHistory", () => {
  it("shows empty state when no movements", () => {
    render(<MovementHistory />);
    expect(screen.getByText("No movements")).toBeInTheDocument();
  });

  it("renders movement rows with type, qty and reference", () => {
    movementsQ.data = { rows: [mv()] };
    render(<MovementHistory />);
    expect(screen.getByText("receipt")).toBeInTheDocument();
    expect(screen.getByText("WIDGET-01")).toBeInTheDocument();
    expect(screen.getByText("PO-1001")).toBeInTheDocument();
  });
});
