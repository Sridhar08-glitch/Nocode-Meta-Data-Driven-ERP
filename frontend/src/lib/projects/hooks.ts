"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type CostSource, type ProjectEntitySlug, projectsApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    // Lifecycle / cost actions mutate the underlying generic project records; refresh the F1.7
    // record caches (keyed ["data", ws, <entity>]) + the entity list so the generic `/e/<entity>`
    // screens update.
    invalidateRecords: () => {
      qc.invalidateQueries({ queryKey: ["data", ws] });
      qc.invalidateQueries({ queryKey: ["entities", ws] });
    },
    // Refresh the native projects panels (cost entries, financials, schedule, resources).
    invalidateProjects: () => {
      qc.invalidateQueries({ queryKey: ["projects", ws] });
    },
  };
}

/** Ensure the PRJ-/TSK- number sequences exist (admin). */
export function useEnsureSetup() {
  return useMutation({ mutationFn: () => projectsApi.setup() });
}

/** Create a PRJ-/TSK-numbered project document (refreshes the generic project screens). */
export function useCreateDocument() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ entitySlug, data }: { entitySlug: ProjectEntitySlug; data: Record<string, unknown> }) =>
      projectsApi.createDocument(entitySlug, data),
    onSuccess: invalidateRecords,
  });
}

// ── lifecycle (single record id) ─────────────────────────────────────────────────

/** Factory: a lifecycle mutation that takes a record id and refreshes the record caches. */
function useIdAction(fn: (recordId: string) => Promise<unknown>) {
  const { invalidateRecords } = useScope();
  return useMutation({ mutationFn: (recordId: string) => fn(recordId), onSuccess: invalidateRecords });
}

export function useStartProject() {
  return useIdAction((id) => projectsApi.startProject(id));
}
export function useCompleteProject() {
  return useIdAction((id) => projectsApi.completeProject(id));
}
export function useApproveBudget() {
  return useIdAction((id) => projectsApi.approveBudget(id));
}
export function useBaselineProject() {
  return useIdAction((id) => projectsApi.baselineProject(id));
}
export function useCompleteTask() {
  return useIdAction((id) => projectsApi.completeTask(id));
}
export function useCompleteMilestone() {
  return useIdAction((id) => projectsApi.completeMilestone(id));
}
export function useApproveTimesheet() {
  return useIdAction((id) => projectsApi.approveTimesheet(id));
}
export function useApproveExpense() {
  return useIdAction((id) => projectsApi.approveExpense(id));
}
export function useApproveChangeRequest() {
  return useIdAction((id) => projectsApi.approveChangeRequest(id));
}
export function useApproveDeliverable() {
  return useIdAction((id) => projectsApi.approveDeliverable(id));
}

// ── native cost-rollup engine ────────────────────────────────────────────────────

/** Cost entries posted against a project. */
export function useCostEntries(projectRecordId: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["projects", ws, "cost-entries", projectRecordId],
    queryFn: () => projectsApi.listCostEntries(projectRecordId!),
    enabled: enabled && !!projectRecordId,
    staleTime: 30_000,
  });
}

/** Post a cost entry against a project (admin). Refreshes the cost-entries list. */
export function usePostCost() {
  const { invalidateProjects } = useScope();
  return useMutation({
    mutationFn: (data: {
      project_record_id: string;
      source: CostSource;
      amount: string;
      description: string;
      entry_date: string;
    }) => projectsApi.postCost(data),
    onSuccess: invalidateProjects,
  });
}

/** Roll posted cost entries onto the project (updates the project record + financials). */
export function useRollupProject() {
  const { invalidateRecords, invalidateProjects } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => projectsApi.rollupProject(recordId),
    onSuccess: () => {
      invalidateRecords();
      invalidateProjects();
    },
  });
}

// ── native read panels ───────────────────────────────────────────────────────────

/** Budget / profitability / EVM + progress for a project. */
export function useProjectFinancials(projectRecordId: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["projects", ws, "financials", projectRecordId],
    queryFn: () => projectsApi.financials(projectRecordId!),
    enabled: enabled && !!projectRecordId,
    staleTime: 15_000,
  });
}

/** Critical-path schedule (duration, critical task ids, gantt bars) for a project. */
export function useProjectSchedule(projectRecordId: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["projects", ws, "schedule", projectRecordId],
    queryFn: () => projectsApi.schedule(projectRecordId!),
    enabled: enabled && !!projectRecordId,
    staleTime: 15_000,
  });
}

/** Resource utilization + allocation conflicts across the workspace. */
export function useResourceUtilization() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["projects", ws, "utilization"],
    queryFn: () => projectsApi.utilization(),
    enabled,
    staleTime: 15_000,
  });
}

/** Resource capacity (allocated vs available hours) for a weekly-hours assumption. */
export function useResourceCapacity(weeklyHours = 40) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["projects", ws, "capacity", weeklyHours],
    queryFn: () => projectsApi.capacity(weeklyHours),
    enabled,
    staleTime: 15_000,
  });
}
