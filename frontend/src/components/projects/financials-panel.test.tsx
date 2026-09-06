import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CostEntry, ProjectFinancials } from "@/lib/projects/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const finQ = { isLoading: false, isError: false, data: null as ProjectFinancials | null };
const entriesQ = { isLoading: false, isError: false, data: [] as CostEntry[] };
const postCost = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const rollup = { mutateAsync: vi.fn(() => Promise.resolve({ total_cost: "5000", by_source: {} })), isPending: false };

vi.mock("@/lib/projects/hooks", () => ({
  useProjectFinancials: () => finQ,
  useCostEntries: () => entriesQ,
  usePostCost: () => postCost,
  useRollupProject: () => rollup,
}));

const tenant = { workspace: { role: "admin" } as { role: string } | null };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));

import { CostEntries, FinancialsCards, PostCostForm } from "./financials-panel";

const financials = (over: Partial<ProjectFinancials> = {}): ProjectFinancials => ({
  budget: {
    planned_budget: "100000", actual_cost: "60000", remaining_budget: "40000",
    budget_variance: "40000", over_budget: false, utilization_percent: 60,
  },
  profitability: { revenue: "150000", cost: "60000", profit: "90000", margin_percent: 60 },
  earned_value: {
    cpi: 1.1, spi: 0.9, cost_variance: "5000", schedule_variance: "-3000",
    estimate_at_completion: "95000",
  },
  progress_percent: 45, task_count: 20, completed_tasks: 9,
  ...over,
});

const arg = (v: unknown) => v as never;

beforeEach(() => {
  finQ.data = null;
  finQ.isLoading = false;
  finQ.isError = false;
  entriesQ.data = [];
  tenant.workspace = { role: "admin" };
  vi.clearAllMocks();
});

describe("FinancialsCards", () => {
  it("renders budget / profitability / EVM / progress from query data", () => {
    finQ.data = financials();
    render(<FinancialsCards projectRecordId="pr-1" />);
    expect(screen.getByText("100000")).toBeInTheDocument(); // planned budget
    expect(screen.getByText("150000")).toBeInTheDocument(); // revenue
    expect(screen.getByText("1.1")).toBeInTheDocument(); // CPI
    expect(screen.getByText("0.9")).toBeInTheDocument(); // SPI
    expect(screen.getByText("45%")).toBeInTheDocument(); // progress
    expect(screen.getByText("60% used")).toBeInTheDocument();
  });

  it("flags an over-budget project", () => {
    finQ.data = financials({
      budget: { planned_budget: "100", actual_cost: "150", remaining_budget: "-50", budget_variance: "-50", over_budget: true, utilization_percent: 150 },
    });
    render(<FinancialsCards projectRecordId="pr-1" />);
    expect(screen.getByText("Over budget")).toBeInTheDocument();
  });
});

describe("PostCostForm", () => {
  it("posts a cost entry against the project", async () => {
    render(<PostCostForm projectRecordId="pr-1" />);
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "1000" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Subcontractor" } });
    fireEvent.click(screen.getByRole("button", { name: "Post cost" }));
    await waitFor(() =>
      expect(postCost.mutateAsync).toHaveBeenCalledWith(
        arg(
          expect.objectContaining({
            project_record_id: "pr-1",
            source: "other",
            amount: "1000",
            description: "Subcontractor",
          }),
        ),
      ),
    );
    expect(toast.success).toHaveBeenCalled();
  });

  it("rejects an empty amount", async () => {
    render(<PostCostForm projectRecordId="pr-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Post cost" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(postCost.mutateAsync).not.toHaveBeenCalled();
  });
});

describe("CostEntries", () => {
  it("prompts to post a cost entry when none exist", () => {
    render(<CostEntries projectRecordId="pr-1" canManage />);
    expect(screen.getByText("No cost entries")).toBeInTheDocument();
  });

  it("rolls up costs onto the project and reports the total", async () => {
    render(<CostEntries projectRecordId="pr-1" canManage />);
    fireEvent.click(screen.getByRole("button", { name: "Roll up" }));
    await waitFor(() => expect(rollup.mutateAsync).toHaveBeenCalledWith(arg("pr-1")));
    expect(toast.success).toHaveBeenCalledWith("Rolled up — total cost 5000");
  });

  it("lists posted cost entries", () => {
    entriesQ.data = [
      { id: "c1", project_record_id: "pr-1", source: "timesheet", amount: "1200", description: "Labor", entry_date: "2026-06-01" },
    ];
    render(<CostEntries projectRecordId="pr-1" canManage />);
    expect(screen.getByText("1200")).toBeInTheDocument();
    expect(screen.getByText("Labor")).toBeInTheDocument();
    expect(screen.getByText("Timesheet")).toBeInTheDocument();
  });

  it("hides the post-cost form for non-managers", () => {
    render(<CostEntries projectRecordId="pr-1" canManage={false} />);
    expect(screen.queryByRole("button", { name: "Post cost" })).not.toBeInTheDocument();
  });
});
