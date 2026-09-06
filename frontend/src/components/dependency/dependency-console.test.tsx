import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  AnalyzeResult,
  ChangePreviewResult,
  ExecutiveSummary,
  PromotionPrecheckResult,
} from "@/lib/dependency/api";

// ---- mocked hooks ----
const objectTypesQ = {
  isLoading: false,
  isError: false,
  data: { object_types: ["entity", "field", "report", "workflow"] },
};
const analyzeQ: { isLoading: boolean; isError: boolean; data?: AnalyzeResult } = {
  isLoading: false,
  isError: false,
  data: undefined,
};
const changePreview = {
  mutateAsync: vi.fn(() => Promise.resolve({} as ChangePreviewResult)),
  isPending: false,
};
const promotion = {
  mutateAsync: vi.fn(() => Promise.resolve({} as PromotionPrecheckResult)),
  isPending: false,
};
const execQ: { isLoading: boolean; isError: boolean; data?: ExecutiveSummary } = {
  isLoading: false,
  isError: false,
  data: undefined,
};

vi.mock("@/lib/dependency/hooks", () => ({
  useObjectTypes: () => objectTypesQ,
  useAnalyze: () => analyzeQ,
  useDependencyGraph: () => ({ isLoading: false, isError: false, data: { nodes: [], edges: [] } }),
  useSafeDelete: () => ({ isLoading: false, isError: false, data: undefined }),
  useChangePreview: () => changePreview,
  usePromotionPrecheck: () => promotion,
  useExecutiveSummary: () => execQ,
}));

import {
  ChangePreviewPanel,
  DependencyConsole,
  ExecutiveSummaryCard,
  ObjectPicker,
  PromotionPrecheckPanel,
  UsedByView,
} from "./dependency-console";

const risk = (over = {}): AnalyzeResult["risk"] => ({
  level: "high",
  count: 3,
  exact: 2,
  has_automation: true,
  score: 0.7,
  ...over,
});

beforeEach(() => {
  analyzeQ.data = undefined;
  execQ.data = undefined;
  changePreview.mutateAsync.mockClear();
  promotion.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("ObjectPicker (data-driven type list)", () => {
  it("populates the type Select from useObjectTypes — not hardcoded", async () => {
    render(<ObjectPicker type="" id="" onType={vi.fn()} onId={vi.fn()} />);
    fireEvent.click(screen.getByRole("combobox", { name: "Object type" }));
    // Every API-provided type renders as an option (humanized via the label map).
    expect(await screen.findByRole("option", { name: "Entity" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Field" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Report" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Workflow" })).toBeInTheDocument();
  });

  it("a new backend type appears automatically (data-driven, no hardcoding)", async () => {
    objectTypesQ.data = { object_types: ["entity", "future_widget"] };
    render(<ObjectPicker type="" id="" onType={vi.fn()} onId={vi.fn()} />);
    fireEvent.click(screen.getByRole("combobox", { name: "Object type" }));
    expect(await screen.findByRole("option", { name: "Future Widget" })).toBeInTheDocument();
    objectTypesQ.data = { object_types: ["entity", "field", "report", "workflow"] };
  });

  it("emits the raw type on selection", async () => {
    const onType = vi.fn();
    render(<ObjectPicker type="" id="" onType={onType} onId={vi.fn()} />);
    fireEvent.click(screen.getByRole("combobox", { name: "Object type" }));
    fireEvent.click(await screen.findByRole("option", { name: "Report" }));
    expect(onType).toHaveBeenCalledWith("report");
  });
});

describe("UsedByView", () => {
  it("renders used-by count + risk badge + by-type breakdown from analyze data", () => {
    analyzeQ.data = {
      object_type: "entity",
      object_id: "lead",
      name: "Lead",
      used_by_count: 5,
      by_type: { report: 2, workflow: 1 },
      dependents: [
        { type: "report", name: "Pipeline", detail: "uses field", approximate: false, id: "r1" },
        { type: "workflow", name: "Auto-assign", detail: "trigger", approximate: true, id: "w1" },
      ],
      risk: risk(),
    };
    render(<UsedByView type="entity" id="lead" />);
    expect(screen.getByText(/Used by/)).toHaveTextContent("Used by 5 objects");
    expect(screen.getByLabelText("Risk: high")).toBeInTheDocument();
    const breakdown = screen.getByLabelText("Dependents by type");
    expect(breakdown).toHaveTextContent("Report: 2");
    expect(breakdown).toHaveTextContent("Workflow: 1");
    // approximate dependents flagged
    expect(screen.getByText("possible match")).toBeInTheDocument();
  });

  it("prompts to pick an object when none selected", () => {
    render(<UsedByView type={null} id={null} />);
    expect(screen.getByText(/Pick an object/)).toBeInTheDocument();
  });
});

describe("ChangePreviewPanel", () => {
  it("sends the change-preview mutateAsync payload", async () => {
    changePreview.mutateAsync.mockResolvedValueOnce({
      direct_impact: 2,
      indirect_impact: 1,
      direct: [],
      risk: risk(),
    } as ChangePreviewResult);
    render(<ChangePreviewPanel />);
    fireEvent.click(screen.getByRole("combobox", { name: "Object type" }));
    fireEvent.click(await screen.findByRole("option", { name: "Entity" }));
    fireEvent.change(screen.getByLabelText("Object id / slug"), { target: { value: "lead" } });
    fireEvent.change(screen.getByLabelText("Change (JSON, optional)"), {
      target: { value: '{"op":"rename"}' },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview impact" }));
    await waitFor(() =>
      expect(changePreview.mutateAsync).toHaveBeenCalledWith({
        object_type: "entity",
        object_id: "lead",
        change: { op: "rename" },
      }),
    );
    expect(await screen.findByText(/Direct:/)).toBeInTheDocument();
  });

  it("rejects invalid JSON without calling the API", async () => {
    render(<ChangePreviewPanel />);
    fireEvent.click(screen.getByRole("combobox", { name: "Object type" }));
    fireEvent.click(await screen.findByRole("option", { name: "Entity" }));
    fireEvent.change(screen.getByLabelText("Object id / slug"), { target: { value: "lead" } });
    fireEvent.change(screen.getByLabelText("Change (JSON, optional)"), {
      target: { value: "{not json" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Preview impact" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/valid JSON/);
    expect(changePreview.mutateAsync).not.toHaveBeenCalled();
  });
});

describe("PromotionPrecheckPanel", () => {
  it("sends the selected objects and renders the risk summary", async () => {
    promotion.mutateAsync.mockResolvedValueOnce({
      blocked: true,
      decision: "blocked by high-risk objects",
      objects: [
        { object_type: "entity", object_id: "lead", name: "Lead", used_by_count: 5, risk: risk() },
        {
          object_type: "field",
          object_id: "status",
          name: "Status",
          used_by_count: 1,
          risk: risk({ level: "low", count: 1 }),
        },
      ],
    } as PromotionPrecheckResult);

    render(<PromotionPrecheckPanel />);
    fireEvent.click(screen.getByRole("combobox", { name: "Promotion object 1 type" }));
    fireEvent.click(await screen.findByRole("option", { name: "Entity" }));
    fireEvent.change(screen.getByLabelText("Promotion object 1 id"), { target: { value: "lead" } });
    fireEvent.click(screen.getByRole("button", { name: "Run precheck" }));

    await waitFor(() =>
      expect(promotion.mutateAsync).toHaveBeenCalledWith([
        { object_type: "entity", object_id: "lead" },
      ]),
    );
    expect(await screen.findByText("Blocked")).toBeInTheDocument();
    const summary = screen.getByLabelText("Risk summary");
    expect(summary).toHaveTextContent("high: 1");
    expect(summary).toHaveTextContent("low: 1");
  });
});

describe("ExecutiveSummaryCard", () => {
  it("renders totals + high-risk count + recent analyses", () => {
    execQ.data = {
      totals: { entities: 12, fields: 80, reports: 5, dashboards: 3, workflows: 7 },
      recent_analyses: [{ object_type: "entity", used_by: 4, risk: "critical", at: "2026-06-24" }],
      high_risk_recent: 2,
    };
    render(<ExecutiveSummaryCard />);
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("High-risk recent")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("used by 4")).toBeInTheDocument();
  });
});

describe("DependencyConsole admin gating", () => {
  it("hides promotion precheck + executive summary for non-admins", () => {
    render(<DependencyConsole isAdmin={false} />);
    expect(screen.queryByText("Promotion precheck")).not.toBeInTheDocument();
    expect(screen.queryByText("Executive summary")).not.toBeInTheDocument();
    // member surfaces remain
    expect(screen.getByText("Used by")).toBeInTheDocument();
  });

  it("shows admin surfaces for admins", () => {
    render(<DependencyConsole isAdmin />);
    expect(screen.getByText("Promotion precheck")).toBeInTheDocument();
    expect(screen.getByText("Executive summary")).toBeInTheDocument();
  });
});
