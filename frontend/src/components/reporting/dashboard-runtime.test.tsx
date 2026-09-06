import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Dashboard, DashboardRunResult } from "@/lib/reporting/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const runState = { data: undefined as DashboardRunResult | undefined, isPending: false, isError: false, mutate: vi.fn() };
vi.mock("@/lib/reporting/hooks", () => ({ useRunDashboard: () => runState }));
const { exportPdf } = vi.hoisted(() => ({ exportPdf: vi.fn(() => Promise.resolve()) }));
vi.mock("@/lib/reporting/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/reporting/api")>()),
  dashboardsApi: { exportPdf },
}));

import { DashboardRuntime } from "./dashboard-runtime";

const dashboard = {
  id: "d1",
  name: "Sales",
  slug: "sales",
  widgets: [
    { id: "w1", widget_type: "metric_card", title: "Total", grid_w: 3 },
    { id: "w2", widget_type: "report", title: "Deals", grid_w: 6 },
    { id: "w3", widget_type: "report", title: "Broken", grid_w: 3 },
  ],
} as unknown as Dashboard;

beforeEach(() => {
  runState.data = undefined;
  runState.isPending = false;
  runState.isError = false;
  runState.mutate.mockClear();
  vi.clearAllMocks();
});

describe("DashboardRuntime", () => {
  it("auto-runs the dashboard on mount", () => {
    render(<DashboardRuntime dashboard={dashboard} />);
    expect(runState.mutate).toHaveBeenCalled();
  });

  it("renders each widget result: metric, table, and isolates a failing widget's error", () => {
    runState.data = {
      dashboard_id: "d1",
      name: "Sales",
      widgets: [
        { widget_id: "w1", widget_type: "metric_card", title: "Total", result: { columns: [{ key: "v", label: "V" }], rows: [{ v: 42 }], total_count: 1, truncated: false } },
        { widget_id: "w2", widget_type: "report", title: "Deals", result: { columns: [{ key: "name", label: "Name" }], rows: [{ name: "Acme" }], total_count: 1, truncated: false } },
        { widget_id: "w3", widget_type: "report", title: "Broken", error: "NQL error: bad field" },
      ],
    };
    render(<DashboardRuntime dashboard={dashboard} />);
    expect(within(screen.getByLabelText("Total")).getByText("42")).toBeInTheDocument(); // metric card
    expect(within(screen.getByLabelText("Deals")).getByText("Acme")).toBeInTheDocument(); // table
    expect(within(screen.getByLabelText("Broken")).getByText("NQL error: bad field")).toBeInTheDocument(); // isolated error
  });

  it("exports the dashboard to PDF", async () => {
    render(<DashboardRuntime dashboard={dashboard} />);
    fireEvent.click(screen.getByRole("button", { name: "Export PDF" }));
    await waitFor(() => expect(exportPdf).toHaveBeenCalledWith("d1", "sales"));
  });

  it("shows the empty state when there are no widgets", () => {
    render(<DashboardRuntime dashboard={{ ...dashboard, widgets: [] }} />);
    expect(screen.getByText("No widgets")).toBeInTheDocument();
  });
});
