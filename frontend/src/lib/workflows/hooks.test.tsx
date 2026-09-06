import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  workflowsApi: {
    listDefinitions: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    getDefinition: vi.fn(() => Promise.resolve({})),
    createDefinition: vi.fn(() => Promise.resolve({ id: "w1" })),
    updateDefinition: vi.fn(() => Promise.resolve({})),
    deleteDefinition: vi.fn(() => Promise.resolve(null)),
    activate: vi.fn(() => Promise.resolve({})),
    pause: vi.fn(() => Promise.resolve({})),
    duplicate: vi.fn(() => Promise.resolve({})),
    listSteps: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    createStep: vi.fn(() => Promise.resolve({})),
    updateStep: vi.fn(() => Promise.resolve({})),
    deleteStep: vi.fn(() => Promise.resolve(null)),
    listEdges: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    createEdge: vi.fn(() => Promise.resolve({})),
    deleteEdge: vi.fn(() => Promise.resolve(null)),
    listRuns: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    getRun: vi.fn(() => Promise.resolve({})),
    cancelRun: vi.fn(() => Promise.resolve({})),
    retryRun: vi.fn(() => Promise.resolve({})),
  },
}));

import { workflowsApi } from "./api";
import {
  useCancelRun,
  useCreateEdge,
  useCreateStep,
  useCreateWorkflow,
  useDeleteEdge,
  useDeleteStep,
  useDeleteWorkflow,
  useDuplicateWorkflow,
  useRetryRun,
  useSetWorkflowStatus,
  useUpdateStep,
  useUpdateWorkflow,
  useWorkflowDefinition,
  useWorkflowDefinitions,
  useWorkflowEdges,
  useWorkflowRun,
  useWorkflowRuns,
  useWorkflowSteps,
} from "./hooks";

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = "W";
  return { qc, wrapper: Wrapper };
}

beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  tenant.isReady = true;
  vi.clearAllMocks();
});

describe("workflow query hooks", () => {
  it("fetch definitions/detail/steps/edges/runs/run when scoped", async () => {
    const { wrapper } = wrap();
    const defs = renderHook(() => useWorkflowDefinitions({ status: "active" }), { wrapper });
    const def = renderHook(() => useWorkflowDefinition("w1"), { wrapper });
    const steps = renderHook(() => useWorkflowSteps("w1"), { wrapper });
    const edges = renderHook(() => useWorkflowEdges("w1"), { wrapper });
    const runs = renderHook(() => useWorkflowRuns({ workflow_id: "w1" }), { wrapper });
    const run = renderHook(() => useWorkflowRun("r1"), { wrapper });
    await waitFor(() => expect(defs.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(def.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(steps.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(edges.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(runs.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(run.result.current.isSuccess).toBe(true));
    expect(workflowsApi.listDefinitions).toHaveBeenCalledWith({ status: "active" });
    expect(workflowsApi.getDefinition).toHaveBeenCalledWith("w1");
    expect(workflowsApi.listSteps).toHaveBeenCalledWith("w1");
    expect(workflowsApi.listEdges).toHaveBeenCalledWith("w1");
    expect(workflowsApi.listRuns).toHaveBeenCalledWith({ workflow_id: "w1" });
    expect(workflowsApi.getRun).toHaveBeenCalledWith("r1");
  });

  it("disables queries without a workspace", () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    const { result } = renderHook(() => useWorkflowDefinitions(), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(workflowsApi.listDefinitions).not.toHaveBeenCalled();
  });
});

describe("workflow mutation hooks", () => {
  it("each mutation calls its API method with the right payload and invalidates", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const run = async <V,>(hook: () => { mutateAsync: (a: V) => Promise<unknown> }, arg: V) => {
      const { result } = renderHook(hook, { wrapper });
      await act(async () => {
        await result.current.mutateAsync(arg);
      });
    };
    await run(useCreateWorkflow, { name: "W", trigger_type: "record_created" as const });
    await run(useUpdateWorkflow, { id: "w1", data: { name: "W2" } });
    await run(useDeleteWorkflow, "w1");
    await run(useSetWorkflowStatus, { id: "w1", action: "activate" as const });
    await run(useSetWorkflowStatus, { id: "w1", action: "pause" as const });
    await run(useDuplicateWorkflow, { id: "w1", slug: "copy" });
    await run(() => useCreateStep("w1"), { step_type: "condition", name: "Check" });
    await run(() => useUpdateStep("w1"), { stepId: "s1", data: { name: "C2" } });
    await run(() => useDeleteStep("w1"), "s1");
    await run(() => useCreateEdge("w1"), { source_step_id: "s1", target_step_id: "s2" });
    await run(() => useDeleteEdge("w1"), "e1");
    await run(useCancelRun, "r1");
    await run(useRetryRun, "r1");

    expect(workflowsApi.createDefinition).toHaveBeenCalledWith({ name: "W", trigger_type: "record_created" });
    expect(workflowsApi.updateDefinition).toHaveBeenCalledWith("w1", { name: "W2" });
    expect(workflowsApi.deleteDefinition).toHaveBeenCalledWith("w1");
    expect(workflowsApi.activate).toHaveBeenCalledWith("w1");
    expect(workflowsApi.pause).toHaveBeenCalledWith("w1");
    expect(workflowsApi.duplicate).toHaveBeenCalledWith("w1", "copy");
    expect(workflowsApi.createStep).toHaveBeenCalledWith("w1", { step_type: "condition", name: "Check" });
    expect(workflowsApi.updateStep).toHaveBeenCalledWith("w1", "s1", { name: "C2" });
    expect(workflowsApi.deleteStep).toHaveBeenCalledWith("w1", "s1");
    expect(workflowsApi.createEdge).toHaveBeenCalledWith("w1", { source_step_id: "s1", target_step_id: "s2" });
    expect(workflowsApi.deleteEdge).toHaveBeenCalledWith("w1", "e1");
    expect(workflowsApi.cancelRun).toHaveBeenCalledWith("r1");
    expect(workflowsApi.retryRun).toHaveBeenCalledWith("r1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["workflows", "acme"] });
  });
});
