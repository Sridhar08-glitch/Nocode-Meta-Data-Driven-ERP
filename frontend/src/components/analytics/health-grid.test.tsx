import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { KpiValue } from "@/lib/analytics/api";

const evalAllQ = { isLoading: false, isError: false, data: [] as KpiValue[] };

vi.mock("@/lib/analytics/hooks", () => ({
  useEvaluateAll: () => evalAllQ,
}));

import { HealthGrid } from "./health-grid";

const v = (over: Partial<KpiValue> = {}): KpiValue => ({
  code: "x",
  name: "X",
  category: "finance",
  value: 1,
  target: 1,
  status: "good",
  variance: 0,
  unit: "",
  available: true,
  ...over,
});

beforeEach(() => {
  evalAllQ.data = [];
});

describe("HealthGrid", () => {
  it("groups evaluated KPIs by category", () => {
    evalAllQ.data = [
      v({ code: "a", name: "Margin", category: "finance", status: "good" }),
      v({ code: "b", name: "Uptime", category: "it", status: "critical" }),
    ];
    render(<HealthGrid />);
    expect(screen.getByText("finance")).toBeInTheDocument();
    expect(screen.getByText("it")).toBeInTheDocument();
    expect(screen.getByText("Margin")).toBeInTheDocument();
    expect(screen.getByText("Uptime")).toBeInTheDocument();
    expect(screen.getByText("good")).toBeInTheDocument();
    expect(screen.getByText("critical")).toBeInTheDocument();
  });

  it("shows an empty state when there are no KPIs", () => {
    render(<HealthGrid />);
    expect(screen.getByText("No KPIs to evaluate")).toBeInTheDocument();
  });
});
