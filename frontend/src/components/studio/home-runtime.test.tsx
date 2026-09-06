import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { HomeLayout } from "@/lib/studio/api";

vi.mock("@/lib/studio/active-app", () => ({ useActiveApp: () => ({ activeAppId: "a1", setActiveApp: vi.fn() }) }));

const resolveQ = { isLoading: false, data: {} as HomeLayout | Record<string, never> };
vi.mock("@/lib/studio/hooks", () => ({ useResolvedHome: () => resolveQ }));

const dashQ = { data: { results: [] as { slug: string }[], count: 0 } };
vi.mock("@/lib/reporting/hooks", () => ({ useDashboards: () => dashQ }));
// DashboardRuntime does network work; stub it so the home runtime can be tested in isolation.
vi.mock("@/components/reporting/dashboard-runtime", () => ({
  DashboardRuntime: ({ dashboard }: { dashboard: { name: string } }) => (
    <div>DASH:{dashboard.name}</div>
  ),
}));

import { HomeRuntime } from "./home-runtime";

beforeEach(() => {
  resolveQ.isLoading = false;
  resolveQ.data = {};
  dashQ.data = { results: [], count: 0 };
});

describe("HomeRuntime", () => {
  it("shows the fallback when no layout resolves", () => {
    render(<HomeRuntime fallback={<div>Welcome fallback</div>} />);
    expect(screen.getByText("Welcome fallback")).toBeInTheDocument();
  });

  it("renders the resolved layout's widgets", () => {
    resolveQ.data = {
      id: "h1", name: "Sales home", scope: "app", target_id: "a1",
      widgets: [{ type: "metric", title: "Open leads", width: 6 }, { type: "report", title: "Pipeline", width: 6 }],
      is_published: true, created_by: null, created_at: "", updated_at: "",
    };
    render(<HomeRuntime fallback={<div>Welcome fallback</div>} />);
    expect(screen.queryByText("Welcome fallback")).not.toBeInTheDocument();
    expect(screen.getByText("Sales home")).toBeInTheDocument();
    expect(screen.getByText("Open leads")).toBeInTheDocument();
    expect(screen.getByText("Pipeline")).toBeInTheDocument();
  });

  it("renders a role dashboard when the layout references one (DG-5 auto-route)", () => {
    dashQ.data = {
      results: [{ slug: "finance_dashboard", name: "Finance Dashboard" } as never],
      count: 1,
    };
    resolveQ.data = {
      id: "h2", name: "Accountant Home", scope: "role", target_id: "role-acct",
      widgets: [{ type: "dashboard", title: "Finance", config: { dashboard_slug: "finance_dashboard" } }],
      is_published: true, created_by: null, created_at: "", updated_at: "",
    };
    render(<HomeRuntime fallback={<div>Welcome fallback</div>} />);
    expect(screen.getByText("DASH:Finance Dashboard")).toBeInTheDocument();
  });

  it("shows a not-found card when the referenced dashboard is missing", () => {
    resolveQ.data = {
      id: "h3", name: "Home", scope: "role", target_id: "r",
      widgets: [{ type: "dashboard", title: "Missing", config: { dashboard_slug: "nope" } }],
      is_published: true, created_by: null, created_at: "", updated_at: "",
    };
    render(<HomeRuntime fallback={<div>Welcome fallback</div>} />);
    expect(screen.getByText("Dashboard not found.")).toBeInTheDocument();
  });
});
