import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Scorecard } from "@/lib/analytics/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const setup = { mutateAsync: vi.fn(() => Promise.resolve({ detail: "ok", created: 5 })), isPending: false };
const snapshot = { mutateAsync: vi.fn(() => Promise.resolve({ snapshotted: 3 })), isPending: false };
const alerts = { mutateAsync: vi.fn(() => Promise.resolve({ alerts: [] })), isPending: false };
let canManage = true;

// useScorecard records the role it was called with so we can assert re-query on switch.
const scorecardSeen: string[] = [];
function buildScorecard(role: string): Scorecard {
  return {
    role,
    kpis: [
      {
        code: `${role}_kpi`,
        name: `${role.toUpperCase()} revenue`,
        category: "finance",
        value: 100,
        target: 90,
        status: "good",
        variance: 10,
        unit: "$",
        available: true,
      },
    ],
    summary: { good: 1, warning: 0, critical: 0, unknown: 0 },
  };
}

vi.mock("@/lib/analytics/hooks", () => ({
  useCanManageAnalytics: () => canManage,
  useEnsureSetup: () => setup,
  useSnapshot: () => snapshot,
  useCheckAlerts: () => alerts,
  useScorecard: (role: string) => {
    scorecardSeen.push(role);
    return { isLoading: false, isError: false, data: buildScorecard(role) };
  },
}));

import { ScorecardActions, ScorecardView } from "./scorecard-view";

beforeEach(() => {
  canManage = true;
  scorecardSeen.length = 0;
  vi.clearAllMocks();
});

describe("ScorecardView", () => {
  it("renders the default (CEO) scorecard with KPI cards and a status badge", () => {
    render(<ScorecardView />);
    expect(scorecardSeen).toContain("ceo");
    expect(screen.getByText("CEO revenue")).toBeInTheDocument();
    expect(screen.getByText("good")).toBeInTheDocument();
    // summary counts
    expect(screen.getByText("1 good")).toBeInTheDocument();
  });

  it("re-queries the scorecard when the role switches", async () => {
    render(<ScorecardView />);
    fireEvent.click(screen.getByLabelText("Executive role"));
    const cfo = await screen.findByRole("option", { name: "CFO" });
    fireEvent.click(cfo);
    await waitFor(() => expect(screen.getByText("CFO revenue")).toBeInTheDocument());
    expect(scorecardSeen).toContain("cfo");
  });

  it("hides admin actions for non-admins", () => {
    canManage = false;
    render(<ScorecardView />);
    expect(screen.queryByRole("button", { name: "Run setup" })).not.toBeInTheDocument();
  });
});

describe("ScorecardActions", () => {
  it("runs setup", async () => {
    render(<ScorecardActions />);
    fireEvent.click(screen.getByRole("button", { name: "Run setup" }));
    await waitFor(() => expect(setup.mutateAsync).toHaveBeenCalled());
  });

  it("snapshots the current period (YYYY-MM)", async () => {
    render(<ScorecardActions />);
    fireEvent.click(screen.getByRole("button", { name: "Snapshot now" }));
    await waitFor(() => expect(snapshot.mutateAsync).toHaveBeenCalled());
    expect((snapshot.mutateAsync.mock.calls as unknown[][])[0][0]).toMatch(/^\d{4}-\d{2}$/);
  });

  it("checks alerts", async () => {
    render(<ScorecardActions />);
    fireEvent.click(screen.getByRole("button", { name: "Check alerts" }));
    await waitFor(() => expect(alerts.mutateAsync).toHaveBeenCalled());
  });
});
