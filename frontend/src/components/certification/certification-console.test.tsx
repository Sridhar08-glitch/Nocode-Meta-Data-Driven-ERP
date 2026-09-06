import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ArchitectureValidation,
  CertificationReport,
  IntegrationRegistry,
  ModuleHealth,
  ReadinessSummary,
  RunAllResult,
  SimulationResult,
} from "@/lib/certification/api";

// ---- mocked hooks (each test sets the `.data` it needs) ----
const reportQ: { isLoading: boolean; isError: boolean; data?: CertificationReport; refetch: () => void } = {
  isLoading: false,
  isError: false,
  data: undefined,
  refetch: vi.fn(),
};
const healthQ: { isLoading: boolean; isError: boolean; data?: ModuleHealth } = {
  isLoading: false,
  isError: false,
  data: undefined,
};
const readinessQ: { isLoading: boolean; isError: boolean; data?: ReadinessSummary } = {
  isLoading: false,
  isError: false,
  data: undefined,
};
const archQ: { isLoading: boolean; isError: boolean; data?: ArchitectureValidation } = {
  isLoading: false,
  isError: false,
  data: undefined,
};
const registryQ: { isLoading: boolean; isError: boolean; data?: IntegrationRegistry } = {
  isLoading: false,
  isError: false,
  data: undefined,
};
const scenariosQ = {
  isLoading: false,
  isError: false,
  data: {
    total: 2,
    scenarios: [
      { key: "trading", name: "Trading", description: "Inv→GL", modules: ["inventory", "ledger"] },
      { key: "manufacturing", name: "Manufacturing", description: "BOM→FG", modules: ["manufacturing"] },
    ],
  },
};
const checklistQ: { isLoading: boolean; isError: boolean; data?: { total: number; checklist: unknown[] } } = {
  isLoading: false,
  isError: false,
  data: { total: 0, checklist: [] },
};
const runOne = {
  mutateAsync: vi.fn((key: string): Promise<SimulationResult> =>
    Promise.resolve({
      scenario: key,
      passed: true,
      steps: [{ name: "step1", status: "passed", detail: "", error: "" }],
      summary: {},
    }),
  ),
  isPending: false,
};
const runAll = {
  mutateAsync: vi.fn((): Promise<RunAllResult> =>
    Promise.resolve({
      total_scenarios: 2,
      passed: 2,
      failed: 0,
      pass_rate_pct: 100,
      scenarios: {
        trading: { passed: true, step_count: 1, failed_steps: [], summary: {} },
        manufacturing: { passed: true, step_count: 1, failed_steps: [], summary: {} },
      },
    }),
  ),
  isPending: false,
};

vi.mock("@/lib/certification/hooks", () => ({
  useCertificationReport: () => reportQ,
  useModuleHealth: () => healthQ,
  useReadiness: () => readinessQ,
  useArchitectureValidation: () => archQ,
  useIntegrationRegistry: () => registryQ,
  useChecklist: () => checklistQ,
  useScenarios: () => scenariosQ,
  useRunScenario: () => runOne,
  useRunAllScenarios: () => runAll,
}));

import {
  ArchitectureValidationPanel,
  CertificationOverview,
  ChecklistPanel,
  IntegrationRegistryPanel,
  ModuleHealthGrid,
  ReadinessGrid,
  SimulationRunner,
} from "./certification-console";

beforeEach(() => {
  reportQ.data = undefined;
  healthQ.data = undefined;
  readinessQ.data = undefined;
  archQ.data = undefined;
  registryQ.data = undefined;
  vi.clearAllMocks();
});

describe("CertificationOverview", () => {
  it("renders the verdict, score and recommendations from the report", () => {
    reportQ.data = {
      report_title: "X",
      generated_at: "2026-06-28T10:00:00Z",
      workspace_id: "ws",
      overall_readiness_score: 95.5,
      overall_health: "healthy",
      readiness_pct: 80,
      sections: [{ name: "Integration Compliance", passed: 20, total: 21, compliance_pct: 95.2, items: [] }],
      integration_health: { total_integrations: 21, certified: 20, partial: 0, deferred: 1, compliance_pct: 95.2 },
      architecture_validation: { engines: {}, overall: "verified", verified_count: 15, total_engines: 15 },
      module_health: { modules: {}, overall: "healthy" },
      executive_readiness: { modules: {}, readiness_pct: 80, total_modules: 12, ready_or_active: 10 },
      recommendations: ["All certification checks passed. System is enterprise-ready."],
      verdict: "ENTERPRISE_CERTIFIED",
    };
    render(<CertificationOverview />);
    expect(screen.getByText("Enterprise certified")).toBeInTheDocument();
    expect(screen.getByText("95.5%")).toBeInTheDocument();
    expect(screen.getByText(/enterprise-ready/i)).toBeInTheDocument();
    expect(screen.getByText("Integration Compliance")).toBeInTheDocument();
  });

  it("shows an error state when the report fails", () => {
    reportQ.isError = true;
    render(<CertificationOverview />);
    expect(screen.getByText(/could not load the certification report/i)).toBeInTheDocument();
    reportQ.isError = false;
  });
});

describe("ModuleHealthGrid", () => {
  it("renders each module with its status and metrics", () => {
    healthQ.data = {
      overall: "warning",
      modules: {
        accounting: { status: "healthy", total_entries: 5, posted: 5 },
        inventory: { status: "warning", negative_stock_lines: 2 },
      },
    };
    render(<ModuleHealthGrid />);
    expect(screen.getByText("Accounting")).toBeInTheDocument();
    expect(screen.getByText("Inventory")).toBeInTheDocument();
    // overall status badge + per-module status badges
    expect(screen.getAllByText("warning").length).toBeGreaterThanOrEqual(2);
  });
});

describe("ReadinessGrid", () => {
  it("renders ERP module readiness states", () => {
    readinessQ.data = {
      readiness_pct: 75,
      total_modules: 2,
      ready_or_active: 1,
      modules: {
        crm: { status: "active", activity_7d: 4, solution_slug: "crm" },
        hr: { status: "not_installed", activity_7d: 0, solution_slug: "hr" },
      },
    };
    render(<ReadinessGrid />);
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("not installed")).toBeInTheDocument();
  });
});

describe("ArchitectureValidationPanel", () => {
  it("lists each engine location and the verified count", () => {
    archQ.data = {
      overall: "verified",
      verified_count: 2,
      total_engines: 2,
      engines: {
        accounting_engine: { status: "verified", location: "apps.ledger.services.GLBus" },
        inventory_engine: { status: "verified", location: "apps.inventory.services.InventoryService" },
      },
    };
    render(<ArchitectureValidationPanel />);
    expect(screen.getByText("2/2 verified")).toBeInTheDocument();
    expect(screen.getByText("apps.ledger.services.GLBus")).toBeInTheDocument();
  });
});

describe("IntegrationRegistryPanel", () => {
  beforeEach(() => {
    registryQ.data = {
      total_integrations: 2,
      certified_count: 1,
      checklist_count: 32,
      by_source: {},
      by_target: {},
      integrations: [
        {
          id: "procurement__inventory",
          source_module: "procurement",
          target_module: "inventory",
          service: "post_goods_receipt → receive",
          trigger: "t",
          event: "e",
          accounting_impact: "Dr 1300 / Cr 2050",
          analytics_impact: "",
          audit_events: [],
          notification_slugs: [],
          idempotency_guard: "",
          status: "certified",
        },
        {
          id: "hr__payroll",
          source_module: "hr",
          target_module: "payroll",
          service: "profile linkage",
          trigger: "t",
          event: "e",
          accounting_impact: "",
          analytics_impact: "",
          audit_events: [],
          notification_slugs: [],
          idempotency_guard: "",
          status: "partial",
        },
      ],
    };
  });

  it("renders all integrations and filters by status", () => {
    render(<IntegrationRegistryPanel />);
    expect(screen.getByText("Procurement → Inventory")).toBeInTheDocument();
    expect(screen.getByText("Hr → Payroll")).toBeInTheDocument();

    // filter to certified-only → the partial one disappears
    fireEvent.click(screen.getByRole("button", { name: "certified" }));
    expect(screen.getByText("Procurement → Inventory")).toBeInTheDocument();
    expect(screen.queryByText("Hr → Payroll")).not.toBeInTheDocument();
  });
});

describe("ChecklistPanel", () => {
  it("renders each module's honest status and the COMPLETE count", () => {
    checklistQ.data = {
      total: 2,
      checklist: [
        { id: "INT-01", name: "Registry", module: "Module 1", status: "COMPLETE" },
        { id: "INT-22", name: "Data integrity", module: "Module 22", status: "PARTIAL" },
      ],
    };
    render(<ChecklistPanel />);
    expect(screen.getByText("1 of 2 modules COMPLETE (evidence-backed)")).toBeInTheDocument();
    expect(screen.getByText("INT-01")).toBeInTheDocument();
    expect(screen.getByText("COMPLETE")).toBeInTheDocument();
    expect(screen.getByText("PARTIAL")).toBeInTheDocument();
  });
});

describe("SimulationRunner", () => {
  it("runs a single scenario and renders its step result", async () => {
    render(<SimulationRunner />);
    const runButtons = screen.getAllByRole("button", { name: "Run" });
    fireEvent.click(runButtons[0]);
    await waitFor(() => expect(runOne.mutateAsync).toHaveBeenCalledWith("trading"));
    expect(await screen.findByText("step1")).toBeInTheDocument();
    // both the scenario-level and step-level "passed" badges render
    expect(screen.getAllByText("passed").length).toBeGreaterThanOrEqual(2);
  });

  it("runs all scenarios then hydrates per-scenario detail", async () => {
    render(<SimulationRunner />);
    fireEvent.click(screen.getByRole("button", { name: "Run all" }));
    await waitFor(() => expect(runAll.mutateAsync).toHaveBeenCalledTimes(1));
    // after run-all it fetches detail for each scenario key
    await waitFor(() => expect(runOne.mutateAsync).toHaveBeenCalledWith("manufacturing"));
    expect(runOne.mutateAsync).toHaveBeenCalledWith("trading");
  });
});
