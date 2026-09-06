import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StandardCost } from "@/lib/manufacturing/api";

const costQ = { isLoading: false, isError: false, data: undefined as StandardCost | undefined };
const costSpy = vi.fn();

vi.mock("@/lib/manufacturing/hooks", () => ({
  useStandardCost: (params: unknown) => {
    costSpy(params);
    return costQ;
  },
}));

import { StandardCostPanel } from "./standard-cost-panel";

beforeEach(() => {
  costQ.data = undefined;
  vi.clearAllMocks();
});

describe("StandardCostPanel", () => {
  it("requests a standard cost with the entered inputs", async () => {
    render(<StandardCostPanel />);
    fireEvent.change(screen.getByLabelText("Product item id"), { target: { value: "prod-1" } });
    fireEvent.change(screen.getByLabelText("Quantity"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Labor minutes"), { target: { value: "60" } });
    fireEvent.change(screen.getByLabelText("Labor rate/hr"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("Overhead %"), { target: { value: "15" } });
    fireEvent.click(screen.getByRole("button", { name: "Calculate" }));
    await waitFor(() =>
      expect(costSpy).toHaveBeenCalledWith({
        product_item_id: "prod-1", quantity: "5", labor_minutes: "60",
        labor_rate_per_hour: "20", overhead_percent: "15",
      }),
    );
  });

  it("renders the cost breakdown", async () => {
    costQ.data = { material: "50", labor: "20", machine: "10", overhead: "12", total: "92" };
    render(<StandardCostPanel />);
    fireEvent.change(screen.getByLabelText("Product item id"), { target: { value: "prod-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Calculate" }));
    await waitFor(() => expect(screen.getByText("92")).toBeInTheDocument());
    expect(screen.getByText("Material")).toBeInTheDocument();
    expect(screen.getByText("Total")).toBeInTheDocument();
  });
});
