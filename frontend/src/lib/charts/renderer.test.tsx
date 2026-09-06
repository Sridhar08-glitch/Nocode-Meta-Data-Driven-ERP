import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Row } from "@/lib/views/types";

// Recharts renders SVG with no size in jsdom; stub it so we test the engine + table + drill, not SVG.
vi.mock("recharts", () => {
  const Stub = ({ children }: { children?: React.ReactNode }) => <div data-recharts>{children}</div>;
  const names = [
    "ResponsiveContainer", "Area", "AreaChart", "Bar", "BarChart", "CartesianGrid", "Cell",
    "ComposedChart", "Funnel", "FunnelChart", "Legend", "Line", "LineChart", "Pie", "PieChart",
    "PolarAngleAxis", "PolarGrid", "Radar", "RadarChart", "RadialBar", "RadialBarChart",
    "Scatter", "ScatterChart", "Tooltip", "Treemap", "XAxis", "YAxis", "ZAxis",
  ];
  return Object.fromEntries(names.map((n) => [n, Stub]));
});

import { CHART_TYPES } from "./registry";
import { ChartRenderer } from "./renderer";
import type { ChartSpec } from "./types";

const rows: Row[] = [
  { id: "1", stage: "open", region: "EU", amount: 100 },
  { id: "2", stage: "open", region: "US", amount: 50 },
  { id: "3", stage: "won", region: "EU", amount: 30 },
];
const spec = (over: Partial<ChartSpec> = {}): ChartSpec => ({
  type: "bar",
  x: { field: "stage" },
  agg: "sum",
  valueField: "amount",
  ...over,
});

describe("ChartRenderer — states", () => {
  it("shows loading, error, empty and unsupported states", () => {
    const { rerender } = render(<ChartRenderer spec={spec()} rows={rows} loading />);
    expect(document.querySelector('[class*="w-full"]')).toBeTruthy(); // skeleton
    rerender(<ChartRenderer spec={spec()} rows={rows} error />);
    expect(screen.getByText("Couldn't load chart data")).toBeInTheDocument();
    rerender(<ChartRenderer spec={spec()} rows={[]} />);
    expect(screen.getByText("No data to chart")).toBeInTheDocument();
    rerender(<ChartRenderer spec={spec({ type: "nope" as ChartSpec["type"] })} rows={rows} />);
    expect(screen.getByText("Unsupported chart type")).toBeInTheDocument();
  });
});

describe("ChartRenderer — dispatch + data table", () => {
  it("dispatches to the render family for the chart type", () => {
    const { rerender } = render(<ChartRenderer spec={spec({ type: "bar" })} rows={rows} />);
    expect(document.querySelector("[data-chart-family]")).toHaveAttribute("data-chart-family", "bar");
    // type switching → different family
    rerender(<ChartRenderer spec={spec({ type: "line" })} rows={rows} />);
    expect(document.querySelector("[data-chart-family]")).toHaveAttribute("data-chart-family", "line");
    rerender(<ChartRenderer spec={spec({ type: "scatter", x: { field: "amount" }, y: { field: "amount" } })} rows={rows} />);
    expect(document.querySelector("[data-chart-family]")).toHaveAttribute("data-chart-family", "scatter");
  });

  it("renders the accessible data table with aggregated values", () => {
    render(<ChartRenderer spec={spec({ type: "bar" })} rows={rows} />);
    const table = screen.getByRole("table");
    expect(within(table).getByText("150")).toBeInTheDocument(); // open sum
    expect(within(table).getByText("30")).toBeInTheDocument(); // won sum
  });
});

describe("ChartRenderer — every registered type renders its figure + table", () => {
  it.each(CHART_TYPES.map((d) => d.type))("renders %s without error", (type) => {
    const def = CHART_TYPES.find((d) => d.type === type)!;
    let s: ChartSpec;
    if (def.dataKind === "xy") {
      s = spec({ type, x: { field: "amount" }, y: { field: "amount" }, sizeField: "amount" });
    } else if (def.dataKind === "multi" || def.dataKind === "matrix") {
      s = spec({ type, series: { field: "region" } });
    } else {
      s = spec({ type });
    }
    render(<ChartRenderer spec={s} rows={rows} />);
    // exercises the ChartCanvas family branch (behavior: a figure renders, not a crash/empty)
    expect(document.querySelector(`[data-chart-family="${def.render}"]`)).toBeTruthy();
  });
});

describe("ChartRenderer — drilldown", () => {
  it("fires onDrill with the selector + resolved records for a single-series category", () => {
    const onDrill = vi.fn();
    render(<ChartRenderer spec={spec({ type: "bar" })} rows={rows} onDrill={onDrill} />);
    fireEvent.click(screen.getByRole("button", { name: "open" }));
    expect(onDrill).toHaveBeenCalledWith(
      { kind: "label", label: "open" },
      expect.arrayContaining([expect.objectContaining({ id: "1" }), expect.objectContaining({ id: "2" })]),
    );
  });

  it("fires onDrill with a cell selector for a multi-series chart", () => {
    const onDrill = vi.fn();
    render(<ChartRenderer spec={spec({ type: "grouped_bar", series: { field: "region" } })} rows={rows} onDrill={onDrill} />);
    // multi-series tables expose per-cell drill buttons; the EU/open cell value is 100
    fireEvent.click(screen.getByRole("button", { name: "100" }));
    expect(onDrill).toHaveBeenCalledWith(
      { kind: "cell", row: "open", col: "EU" },
      [expect.objectContaining({ id: "1" })],
    );
  });

  it("does not render drill buttons without an onDrill handler", () => {
    render(<ChartRenderer spec={spec({ type: "bar" })} rows={rows} />);
    expect(screen.queryByRole("button", { name: "open" })).not.toBeInTheDocument();
  });
});
