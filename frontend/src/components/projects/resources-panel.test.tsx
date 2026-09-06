import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ResourceCapacity, ResourceUtilization } from "@/lib/projects/api";

const utilQ = { isLoading: false, isError: false, data: null as ResourceUtilization | null };
const capQ = { isLoading: false, isError: false, data: null as ResourceCapacity | null };
const capacitySpy = vi.fn();

vi.mock("@/lib/projects/hooks", () => ({
  useResourceUtilization: () => utilQ,
  useResourceCapacity: (hours: number) => {
    capacitySpy(hours);
    return capQ;
  },
}));

import { CapacityTable, UtilizationTable } from "./resources-panel";

beforeEach(() => {
  utilQ.data = null;
  utilQ.isLoading = false;
  utilQ.isError = false;
  capQ.data = null;
  capQ.isLoading = false;
  capQ.isError = false;
  vi.clearAllMocks();
});

describe("UtilizationTable", () => {
  it("renders utilization rows + over-allocated status and conflicts", () => {
    utilQ.data = {
      utilization: [
        { employee: "emp-abc12345", total_percent: 120, over_allocated: true, available_percent: -20 },
        { employee: "emp-def67890", total_percent: 80, over_allocated: false, available_percent: 20 },
      ],
      conflicts: [{ employee: "emp-abc12345" }],
    };
    render(<UtilizationTable />);
    expect(screen.getByText("120%")).toBeInTheDocument();
    expect(screen.getByText("Over-allocated")).toBeInTheDocument();
    expect(screen.getByText("1 allocation conflict")).toBeInTheDocument();
  });

  it("shows an empty state with no utilization data", () => {
    utilQ.data = { utilization: [], conflicts: [] };
    render(<UtilizationTable />);
    expect(screen.getByText("No utilization data")).toBeInTheDocument();
  });
});

describe("CapacityTable", () => {
  it("renders capacity rows + over-capacity status", () => {
    capQ.data = {
      capacity: [
        { employee: "emp-abc12345", allocated_hours: 48, available_hours: -8, over_capacity: true },
        { employee: "emp-def67890", allocated_hours: 32, available_hours: 8, over_capacity: false },
      ],
    };
    render(<CapacityTable />);
    expect(screen.getByText("48")).toBeInTheDocument();
    expect(screen.getByText("Over capacity")).toBeInTheDocument();
  });

  it("re-queries capacity for a new weekly-hours assumption", () => {
    capQ.data = { capacity: [] };
    render(<CapacityTable />);
    // default 40 requested initially
    expect(capacitySpy).toHaveBeenCalledWith(40);
    fireEvent.change(screen.getByLabelText("Weekly hours"), { target: { value: "35" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(capacitySpy).toHaveBeenCalledWith(35);
  });
});
