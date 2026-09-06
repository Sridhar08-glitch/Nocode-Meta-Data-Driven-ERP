import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
  apiSend: vi.fn(() => Promise.resolve({})),
}));

import { apiGet, apiSend } from "@/lib/api/request";

import { workflowsApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("workflowsApi definitions", () => {
  it("lists with filters and CRUDs", () => {
    workflowsApi.listDefinitions();
    workflowsApi.listDefinitions({ trigger_type: "record_created", status: "active" });
    workflowsApi.getDefinition("w1");
    workflowsApi.createDefinition({ name: "Lead intake", trigger_type: "record_created" });
    workflowsApi.updateDefinition("w1", { name: "X" });
    workflowsApi.deleteDefinition("w1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/workflows/definitions/");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/workflows/definitions/?trigger_type=record_created&status=active",
    );
    expect(apiGet).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/", "POST", {
      name: "Lead intake",
      trigger_type: "record_created",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/", "PATCH", { name: "X" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/", "DELETE");
  });

  it("activates, pauses and duplicates", () => {
    workflowsApi.activate("w1");
    workflowsApi.pause("w1");
    workflowsApi.duplicate("w1");
    workflowsApi.duplicate("w1", "copy-slug");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/activate/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/pause/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/duplicate/", "POST", {});
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/duplicate/", "POST", {
      slug: "copy-slug",
    });
  });
});

describe("workflowsApi steps + edges", () => {
  it("CRUDs steps", () => {
    workflowsApi.listSteps("w1");
    workflowsApi.createStep("w1", { step_type: "action_send_email", name: "Notify" });
    workflowsApi.updateStep("w1", "s1", { name: "Notify2" });
    workflowsApi.deleteStep("w1", "s1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/steps/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/steps/", "POST", {
      step_type: "action_send_email",
      name: "Notify",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/steps/s1/", "PATCH", {
      name: "Notify2",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/steps/s1/", "DELETE");
  });

  it("creates and deletes edges", () => {
    workflowsApi.listEdges("w1");
    workflowsApi.createEdge("w1", { source_step_id: "s1", target_step_id: "s2", condition_label: "true" });
    workflowsApi.deleteEdge("w1", "e1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/edges/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/edges/", "POST", {
      source_step_id: "s1",
      target_step_id: "s2",
      condition_label: "true",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/definitions/w1/edges/e1/", "DELETE");
  });
});

describe("workflowsApi runs", () => {
  it("lists (filtered), gets, cancels, retries", () => {
    workflowsApi.listRuns({ workflow_id: "w1", status: "failed" });
    workflowsApi.getRun("r1");
    workflowsApi.cancelRun("r1");
    workflowsApi.retryRun("r1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/workflows/runs/?workflow_id=w1&status=failed");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/workflows/runs/r1/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/runs/r1/cancel/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/workflows/runs/r1/retry/", "POST");
  });
});
