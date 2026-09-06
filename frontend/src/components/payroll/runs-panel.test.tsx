import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PayrollRun } from "@/lib/payroll/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

// Stub the child panels so this test isolates the runs-for-period flow.
vi.mock("./periods-panel", () => ({
  PeriodsPanel: ({ onSelect }: { onSelect: (id: string) => void }) => (
    <button onClick={() => onSelect("p1")}>pick-period</button>
  ),
}));
vi.mock("./run-lifecycle", () => ({
  RunLifecycle: ({ runId }: { runId: string }) => <div>lifecycle:{runId}</div>,
}));

const runsQ = { isLoading: false, isError: false, data: [] as PayrollRun[] };
const createRun = { mutateAsync: vi.fn(() => Promise.resolve({ id: "r5" })), isPending: false };
let canManage = true;

vi.mock("@/lib/payroll/hooks", () => ({
  useRuns: () => runsQ,
  useCreateRun: () => createRun,
  useCanManagePayroll: () => canManage,
}));

import { RunsPanel } from "./runs-panel";

beforeEach(() => {
  runsQ.data = [];
  canManage = true;
  vi.clearAllMocks();
});

describe("RunsPanel", () => {
  it("prompts to select a run before a period is chosen", () => {
    render(<RunsPanel />);
    expect(screen.getByText("No run selected")).toBeInTheDocument();
  });

  it("creates a run for the selected period and selects it", async () => {
    render(<RunsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "pick-period" }));
    fireEvent.click(await screen.findByRole("button", { name: "New run" }));
    await waitFor(() => expect(createRun.mutateAsync).toHaveBeenCalledWith("p1"));
    // The created run id flows into the lifecycle panel.
    expect(await screen.findByText("lifecycle:r5")).toBeInTheDocument();
  });

  it("hides New run for non-admins", async () => {
    canManage = false;
    render(<RunsPanel />);
    fireEvent.click(screen.getByRole("button", { name: "pick-period" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "New run" })).not.toBeInTheDocument());
  });
});
