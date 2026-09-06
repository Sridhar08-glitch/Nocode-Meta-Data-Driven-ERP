import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TenantHealth } from "@/lib/admin/api";

const healthQ = {
  isLoading: false,
  isError: false,
  data: {
    workspace_id: "w1", generated_at: "",
    workflows: { total: 40, completed: 36, failed: 4, running: 0, queued: 0, success_rate: 0.9 },
    workflow_latency_ms: { p50: 120, p95: 800, p99: null, count: 40 },
    activity: { dau: 5, wau: 12, mau: 30 },
    records: { created_24h: 7, created_7d: 50, created_total: 900 },
    errors: { workflow_runs_24h: 10, workflow_failures_24h: 1, error_rate_24h: 0.1 },
    storage: { entity_count: 8, row_count_estimate: 1234 },
    api_latency_ms: null, queue: null, plan_limits: null, ai: null,
  } as TenantHealth,
};
vi.mock("@/lib/admin/hooks", () => ({ useTenantHealth: () => healthQ }));

import { TenantHealthPanel } from "./tenant-health";

describe("TenantHealthPanel", () => {
  it("renders KPI values incl. derived percentages and a dash for null latency", () => {
    render(<TenantHealthPanel />);
    expect(within(screen.getByLabelText("Success rate")).getByText("90%")).toBeInTheDocument();
    expect(within(screen.getByLabelText("DAU")).getByText("5")).toBeInTheDocument();
    expect(within(screen.getByLabelText("p99")).getByText("—")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Error rate")).getByText("10%")).toBeInTheDocument();
  });
});
