"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  workflowsApi,
  type WorkflowDefinitionWrite,
  type WorkflowEdgeWrite,
  type WorkflowStepWrite,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => qc.invalidateQueries({ queryKey: ["workflows", ws] }),
  };
}

// ── definitions ─────────────────────────────────────────────────────────────────────
export function useWorkflowDefinitions(params: { trigger_type?: string; status?: string } = {}) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["workflows", ws, "definitions", params],
    queryFn: () => workflowsApi.listDefinitions(params),
    enabled,
    staleTime: 30_000,
  });
}

export function useWorkflowDefinition(id: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["workflows", ws, "definition", id],
    queryFn: () => workflowsApi.getDefinition(id),
    enabled: enabled && !!id,
  });
}

export function useCreateWorkflow() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (data: WorkflowDefinitionWrite) => workflowsApi.createDefinition(data),
    onSuccess: invalidate,
  });
}
export function useUpdateWorkflow() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<WorkflowDefinitionWrite> }) =>
      workflowsApi.updateDefinition(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteWorkflow() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => workflowsApi.deleteDefinition(id), onSuccess: invalidate });
}
export function useSetWorkflowStatus() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: "activate" | "pause" }) =>
      action === "activate" ? workflowsApi.activate(id) : workflowsApi.pause(id),
    onSuccess: invalidate,
  });
}
export function useDuplicateWorkflow() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, slug }: { id: string; slug?: string }) => workflowsApi.duplicate(id, slug),
    onSuccess: invalidate,
  });
}

// ── steps ─────────────────────────────────────────────────────────────────────────────
export function useWorkflowSteps(defId: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["workflows", ws, "steps", defId],
    queryFn: () => workflowsApi.listSteps(defId),
    enabled: enabled && !!defId,
  });
}
export function useCreateStep(defId: string) {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (data: WorkflowStepWrite) => workflowsApi.createStep(defId, data),
    onSuccess: invalidate,
  });
}
export function useUpdateStep(defId: string) {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ stepId, data }: { stepId: string; data: Partial<WorkflowStepWrite> }) =>
      workflowsApi.updateStep(defId, stepId, data),
    onSuccess: invalidate,
  });
}
export function useDeleteStep(defId: string) {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (stepId: string) => workflowsApi.deleteStep(defId, stepId),
    onSuccess: invalidate,
  });
}

// ── edges ─────────────────────────────────────────────────────────────────────────────
export function useWorkflowEdges(defId: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["workflows", ws, "edges", defId],
    queryFn: () => workflowsApi.listEdges(defId),
    enabled: enabled && !!defId,
  });
}
export function useCreateEdge(defId: string) {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (data: WorkflowEdgeWrite) => workflowsApi.createEdge(defId, data),
    onSuccess: invalidate,
  });
}
export function useDeleteEdge(defId: string) {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (edgeId: string) => workflowsApi.deleteEdge(defId, edgeId),
    onSuccess: invalidate,
  });
}

// ── runs ──────────────────────────────────────────────────────────────────────────────
export function useWorkflowRuns(params: { workflow_id?: string; status?: string } = {}) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["workflows", ws, "runs", params],
    queryFn: () => workflowsApi.listRuns(params),
    enabled,
    staleTime: 10_000,
  });
}
export function useWorkflowRun(runId: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["workflows", ws, "run", runId],
    queryFn: () => workflowsApi.getRun(runId),
    enabled: enabled && !!runId,
  });
}
export function useCancelRun() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (runId: string) => workflowsApi.cancelRun(runId), onSuccess: invalidate });
}
export function useRetryRun() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (runId: string) => workflowsApi.retryRun(runId), onSuccess: invalidate });
}
