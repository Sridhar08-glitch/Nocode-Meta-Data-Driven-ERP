import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Row } from "@/lib/views/types";

import { ChartView } from "./chart-view";
import { DashboardView } from "./dashboard-view";
import { GanttView } from "./gantt-view";
import { HierarchyView } from "./hierarchy-view";
import { MapView } from "./map-view";
import { PivotView } from "./pivot-view";
import { TimelineView } from "./timeline-view";

describe("HierarchyView", () => {
  const rows: Row[] = [
    { id: "1", name: "CEO", mgr: null },
    { id: "2", name: "VP", mgr: "1" },
    { id: "3", name: "IC", mgr: "2" },
  ];
  it("renders an indented tree (depth via padding)", () => {
    render(<HierarchyView rows={rows} parentField="mgr" labelField="name" layout="tree" />);
    const items = within(screen.getByRole("list", { name: "Tree" })).getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual(["▸CEO", "▸VP", "•IC"]);
    expect(items[2]).toHaveStyle({ paddingLeft: "32px" }); // depth 2
  });
  it("renders org boxes", () => {
    render(<HierarchyView rows={rows} parentField="mgr" labelField="name" layout="org" />);
    expect(screen.getByLabelText("Org chart")).toBeInTheDocument();
    expect(screen.getByText("CEO")).toBeInTheDocument();
  });
  it("shows an empty message with no rows", () => {
    render(<HierarchyView rows={[]} parentField="mgr" />);
    expect(screen.getByText("No records to chart.")).toBeInTheDocument();
  });
});

describe("TimelineView", () => {
  it("lists events newest-first by default", () => {
    const rows: Row[] = [
      { id: "a", at: "2026-01-01", name: "Old" },
      { id: "b", at: "2026-03-01", name: "New" },
    ];
    render(<TimelineView rows={rows} dateField="at" titleField="name" />);
    const items = within(screen.getByRole("list", { name: "Timeline" })).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("New");
    expect(items[1]).toHaveTextContent("Old");
  });
});

describe("MapView", () => {
  it("plots a marker per located row", () => {
    const rows: Row[] = [
      { id: "1", lat: 50, lng: 0, name: "A" },
      { id: "2", lat: 10, lng: 20, name: "B" },
    ];
    render(<MapView rows={rows} latField="lat" lngField="lng" labelField="name" />);
    expect(screen.getByLabelText("Map with 2 markers")).toBeInTheDocument();
    expect(screen.getByLabelText("A")).toHaveStyle({ top: "0%" }); // northmost at top
  });
});

describe("PivotView", () => {
  // values chosen so the EU/won cell (30) is unique across all cells + row/col/grand totals
  const rows: Row[] = [
    { id: "1", region: "EU", stage: "open", v: 100 },
    { id: "2", region: "EU", stage: "won", v: 30 },
    { id: "3", region: "US", stage: "open", v: 7 },
    { id: "4", region: "US", stage: "won", v: 70 },
  ];
  it("renders aggregated cells + totals", () => {
    render(<PivotView rows={rows} rowField="region" colField="stage" valueField="v" agg="sum" />);
    expect(screen.getByText("30")).toBeInTheDocument(); // EU/won cell (unique)
    expect(screen.getByText("207")).toBeInTheDocument(); // grand total
  });
  it("invokes the drill-down callback with the cell keys", () => {
    const onDrill = vi.fn();
    render(<PivotView rows={rows} rowField="region" colField="stage" valueField="v" agg="sum" onDrill={onDrill} />);
    fireEvent.click(screen.getByRole("button", { name: "30" }));
    expect(onDrill).toHaveBeenCalledWith("EU", "won");
  });
});

describe("GanttView", () => {
  it("renders a bar per dated row with progress", () => {
    const rows: Row[] = [
      { id: "1", name: "T1", s: "2026-01-01", e: "2026-01-10", pct: 40 },
      { id: "2", name: "T2", s: "2026-01-05", e: "2026-01-15", pct: 0 },
    ];
    render(<GanttView rows={rows} config={{ startField: "s", endField: "e", labelField: "name", progressField: "pct" }} />);
    expect(screen.getByLabelText("T1 bar")).toHaveAttribute("data-progress", "0.4");
    expect(screen.getByLabelText("T2 bar")).toBeInTheDocument();
  });
  it("shows an empty message when no rows have valid dates", () => {
    render(<GanttView rows={[]} config={{ startField: "s", endField: "e" }} />);
    expect(screen.getByText(/No records with valid start\/end/)).toBeInTheDocument();
  });
});

describe("ChartView", () => {
  it("renders a bar per group with the aggregated value", () => {
    const rows: Row[] = [
      { id: "1", stage: "open", v: 10 },
      { id: "2", stage: "open", v: 20 },
      { id: "3", stage: "won", v: 5 },
    ];
    render(<ChartView rows={rows} chartType="bar" groupField="stage" valueField="v" agg="sum" />);
    const bars = screen.getAllByTestId("chart-bar");
    expect(bars.map((b) => b.getAttribute("data-value"))).toEqual(["30", "5"]);
  });
});

describe("DashboardView", () => {
  it("composes metric + chart widgets over shared aggregations", () => {
    const rows: Row[] = [
      { id: "1", stage: "open", v: 10 },
      { id: "2", stage: "won", v: 20 },
    ];
    render(
      <DashboardView
        rows={rows}
        widgets={[
          { id: "m", title: "Total value", kind: "metric", config: { valueField: "v", agg: "sum" } },
          { id: "c", title: "By stage", kind: "chart", config: { chartType: "bar", groupField: "stage", valueField: "v", agg: "sum" } },
        ]}
      />,
    );
    expect(within(screen.getByLabelText("Total value")).getByText("30")).toBeInTheDocument();
    expect(screen.getByLabelText("By stage")).toBeInTheDocument();
  });
  it("shows an empty message with no widgets", () => {
    render(<DashboardView rows={[]} widgets={[]} />);
    expect(screen.getByText("No widgets.")).toBeInTheDocument();
  });
});
