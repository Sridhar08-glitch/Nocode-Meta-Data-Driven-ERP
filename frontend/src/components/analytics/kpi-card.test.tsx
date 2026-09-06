import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { KpiValue } from "@/lib/analytics/api";

import { KpiCard } from "./kpi-card";

const kpi = (over: Partial<KpiValue> = {}): KpiValue => ({
  code: "gross_margin",
  name: "Gross margin",
  category: "finance",
  value: 42,
  target: 40,
  status: "good",
  variance: 2,
  unit: "%",
  available: true,
  ...over,
});

describe("KpiCard", () => {
  it("renders name, value, unit, target and status badge", () => {
    render(<KpiCard kpi={kpi()} />);
    expect(screen.getByText("Gross margin")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("good")).toBeInTheDocument();
    expect(screen.getByText(/Target 40/)).toBeInTheDocument();
  });

  it("shows em-dash and no unit when the KPI is unavailable", () => {
    render(<KpiCard kpi={kpi({ available: false, status: "unknown", value: null })} />);
    expect(screen.getByText("unknown")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders the critical status", () => {
    render(<KpiCard kpi={kpi({ status: "critical" })} />);
    expect(screen.getByText("critical")).toBeInTheDocument();
  });
});
