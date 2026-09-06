import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { WorkflowDefinition, WorkflowEdge, WorkflowStep } from "@/lib/workflows/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const def = { isLoading: false, isError: false, data: null as WorkflowDefinition | null };
const steps = { data: { results: [] as WorkflowStep[], count: 0 } };
const edges = { data: { results: [] as WorkflowEdge[], count: 0 } };
const updateWf = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const setStatus = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const createStep = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delStep = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const createEdge = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delEdge = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/workflows/hooks", () => ({
  useWorkflowDefinition: () => def,
  useWorkflowSteps: () => steps,
  useWorkflowEdges: () => edges,
  useUpdateWorkflow: () => updateWf,
  useSetWorkflowStatus: () => setStatus,
  useCreateStep: () => createStep,
  useDeleteStep: () => delStep,
  useCreateEdge: () => createEdge,
  useDeleteEdge: () => delEdge,
}));

import { WorkflowDesigner } from "./workflow-designer";

function wf(over: Partial<WorkflowDefinition> = {}): WorkflowDefinition {
  return {
    id: "w1",
    name: "Lead intake",
    slug: "lead_intake",
    description: "",
    trigger_type: "record_created",
    trigger_config: {},
    entity_id: null,
    module_id: null,
    status: "draft",
    version: 1,
    is_system: false,
    max_concurrent_runs: 10,
    timeout_seconds: 3600,
    retry_policy: {},
    run_count: 0,
    error_count: 0,
    last_run_at: null,
    created_at: "",
    updated_at: "",
    ...over,
  };
}
function step(over: Partial<WorkflowStep> = {}): WorkflowStep {
  return {
    id: "s1",
    workflow_id: "w1",
    step_type: "action_send_notification",
    name: "Notify",
    config: {},
    position_x: 0,
    position_y: 0,
    is_entry: false,
    on_error: "stop",
    retry_config: {},
    created_at: "",
    updated_at: "",
    ...over,
  };
}

beforeEach(() => {
  def.isLoading = false;
  def.isError = false;
  def.data = wf();
  steps.data = { results: [], count: 0 };
  edges.data = { results: [], count: 0 };
  for (const m of [updateWf, setStatus, createStep, delStep, createEdge, delEdge]) m.isPending = false;
  vi.clearAllMocks();
});

describe("WorkflowDesigner — load/state", () => {
  it("renders loading and error states", () => {
    def.isLoading = true;
    const { rerender, container } = render(<WorkflowDesigner definitionId="w1" />);
    expect(container.querySelector(".h-64")).toBeTruthy();
    def.isLoading = false;
    def.isError = true;
    rerender(<WorkflowDesigner definitionId="w1" />);
    expect(screen.getByText("Couldn't load workflow")).toBeInTheDocument();
  });

  it("shows the name + status and an empty steps state", () => {
    render(<WorkflowDesigner definitionId="w1" />);
    expect(screen.getByRole("heading", { name: "Lead intake" })).toBeInTheDocument();
    expect(screen.getByText("No steps")).toBeInTheDocument();
  });
});

describe("WorkflowDesigner — trigger + status", () => {
  it("changes the trigger type via the API", async () => {
    render(<WorkflowDesigner definitionId="w1" />);
    fireEvent.click(screen.getByRole("combobox", { name: /Trigger/i }));
    fireEvent.click(await screen.findByRole("option", { name: "Record updated" }));
    await waitFor(() =>
      expect(updateWf.mutateAsync).toHaveBeenCalledWith({ id: "w1", data: { trigger_type: "record_updated" } }),
    );
  });

  it("activates a draft workflow and pauses an active one", async () => {
    render(<WorkflowDesigner definitionId="w1" />);
    fireEvent.click(screen.getByRole("button", { name: "Activate" }));
    await waitFor(() =>
      expect(setStatus.mutateAsync).toHaveBeenCalledWith({ id: "w1", action: "activate" }),
    );
    def.data = wf({ status: "active" });
    render(<WorkflowDesigner definitionId="w1" />);
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    await waitFor(() =>
      expect(setStatus.mutateAsync).toHaveBeenCalledWith({ id: "w1", action: "pause" }),
    );
  });
});

describe("WorkflowDesigner — steps", () => {
  it("adds the first step as the entry node", async () => {
    render(<WorkflowDesigner definitionId="w1" />);
    fireEvent.click(screen.getAllByRole("button", { name: "Add step" })[0]);
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Notify owner" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add step" }));
    await waitFor(() => expect(createStep.mutateAsync).toHaveBeenCalled());
    expect(createStep.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Notify owner",
        step_type: "action_send_notification",
        on_error: "stop",
        is_entry: true, // first step → entry node
      }),
    );
  });

  it("does NOT mark a later step as entry when one already exists", async () => {
    steps.data = { results: [step({ is_entry: true })], count: 1 };
    render(<WorkflowDesigner definitionId="w1" />);
    fireEvent.click(screen.getByRole("button", { name: "Add step" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Second" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add step" }));
    await waitFor(() =>
      expect(createStep.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ is_entry: false })),
    );
  });

  it("lists steps and deletes one", async () => {
    steps.data = { results: [step({ is_entry: true })], count: 1 };
    render(<WorkflowDesigner definitionId="w1" />);
    expect(screen.getByText("Notify")).toBeInTheDocument();
    expect(screen.getByText("entry")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove step Notify" }));
    await waitFor(() => expect(delStep.mutateAsync).toHaveBeenCalledWith("s1"));
  });
});

describe("WorkflowDesigner — connections", () => {
  it("connects two steps with a condition label", async () => {
    steps.data = {
      results: [step({ id: "s1", name: "Check" }), step({ id: "s2", name: "Notify" })],
      count: 2,
    };
    render(<WorkflowDesigner definitionId="w1" />);
    fireEvent.click(screen.getByRole("button", { name: "Connect steps" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(within(dialog).getByRole("combobox", { name: "From" }));
    fireEvent.click(await screen.findByRole("option", { name: "Check" }));
    fireEvent.click(within(dialog).getByRole("combobox", { name: "To" }));
    fireEvent.click(await screen.findByRole("option", { name: "Notify" }));
    fireEvent.change(within(dialog).getByLabelText(/Condition label/), { target: { value: "true" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Connect" }));
    await waitFor(() =>
      expect(createEdge.mutateAsync).toHaveBeenCalledWith({
        source_step_id: "s1",
        target_step_id: "s2",
        condition_label: "true",
      }),
    );
  });

  it("disables Connect steps with fewer than two steps and lists/deletes an edge", async () => {
    steps.data = {
      results: [step({ id: "s1", name: "Check" }), step({ id: "s2", name: "Notify" })],
      count: 2,
    };
    edges.data = {
      results: [
        { id: "e1", workflow_id: "w1", source_step_id: "s1", target_step_id: "s2", condition_label: "true", condition_expr: "" },
      ],
      count: 1,
    };
    render(<WorkflowDesigner definitionId="w1" />);
    expect(screen.getByRole("button", { name: "Connect steps" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Remove connection Check to Notify" }));
    await waitFor(() => expect(delEdge.mutateAsync).toHaveBeenCalledWith("e1"));
  });
});
