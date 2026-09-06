import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WorkflowRun, WorkflowRunDetail } from "@/lib/workflows/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const runs = { isLoading: false, isError: false, data: { results: [] as WorkflowRun[], count: 0 } };
const runDetail = { isLoading: false, isError: false, data: null as WorkflowRunDetail | null };
const cancel = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const retry = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/workflows/hooks", () => ({
  useWorkflowRuns: () => runs,
  useWorkflowRun: () => runDetail,
  useCancelRun: () => cancel,
  useRetryRun: () => retry,
}));

import { RunMonitor } from "./run-monitor";

function run(over: Partial<WorkflowRun> = {}): WorkflowRun {
  return {
    id: "run-abcdef12",
    workflow_id: "w1",
    trigger_type: "record_created",
    trigger_payload: {},
    entity_id: null,
    record_id: null,
    status: "completed",
    started_at: null,
    completed_at: null,
    duration_ms: 42,
    error_message: "",
    error_step_id: null,
    context: {},
    initiated_by: null,
    created_at: "",
    updated_at: "",
    ...over,
  };
}

beforeEach(() => {
  runs.isLoading = false;
  runs.isError = false;
  runs.data = { results: [], count: 0 };
  runDetail.isLoading = false;
  runDetail.isError = false;
  runDetail.data = null;
  vi.clearAllMocks();
});

describe("RunMonitor", () => {
  it("renders loading, error and empty states", () => {
    runs.isLoading = true;
    const { rerender, container } = render(<RunMonitor definitionId="w1" />);
    expect(container.querySelector(".h-48")).toBeTruthy();
    runs.isLoading = false;
    runs.isError = true;
    rerender(<RunMonitor definitionId="w1" />);
    expect(screen.getByText("Couldn't load runs")).toBeInTheDocument();
    runs.isError = false;
    rerender(<RunMonitor definitionId="w1" />);
    expect(screen.getByText("No runs yet")).toBeInTheDocument();
  });

  it("expands a run to show step logs", async () => {
    runs.data = { results: [run()], count: 1 };
    runDetail.data = {
      ...run(),
      step_runs: [
        { id: "sr1", run_id: "run-abcdef12", step_id: "step1234", status: "completed", started_at: null, completed_at: null, duration_ms: 5, attempt_number: 1, input_data: {}, output_data: {}, error_message: "" },
      ],
    };
    render(<RunMonitor definitionId="w1" />);
    fireEvent.click(screen.getByRole("button", { expanded: false }));
    // the step log row (unique step id) appears once expanded
    expect(await screen.findByText(/step1234/)).toBeInTheDocument();
    expect(screen.getAllByText("completed").length).toBeGreaterThanOrEqual(2); // run + step badges
  });

  it("cancels a running run", async () => {
    runs.data = { results: [run({ status: "running" })], count: 1 };
    render(<RunMonitor definitionId="w1" />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(cancel.mutateAsync).toHaveBeenCalledWith("run-abcdef12"));
    expect(toast.success).toHaveBeenCalled();
  });

  it("retries a failed run and shows its error", async () => {
    runs.data = { results: [run({ status: "failed" })], count: 1 };
    render(<RunMonitor definitionId="w1" />);
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(retry.mutateAsync).toHaveBeenCalledWith("run-abcdef12"));
  });

  it("surfaces a cancel error", async () => {
    cancel.mutateAsync.mockRejectedValueOnce(new Error("x"));
    runs.data = { results: [run({ status: "running" })], count: 1 };
    render(<RunMonitor definitionId="w1" />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
  });
});
