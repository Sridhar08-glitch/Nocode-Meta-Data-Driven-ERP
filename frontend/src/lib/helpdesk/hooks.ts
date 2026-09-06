"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type AutoAssignMethod, type HelpdeskEntitySlug, helpdeskApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    // Lifecycle / CSAT actions mutate the underlying generic helpdesk records; refresh the F1.7 record
    // caches (keyed ["data", ws, <entity>]) + the entity list so the generic `/e/<entity>` screens update.
    invalidateRecords: () => {
      qc.invalidateQueries({ queryKey: ["data", ws] });
      qc.invalidateQueries({ queryKey: ["entities", ws] });
    },
    // Refresh the native helpdesk panels (knowledge recommendation, SLA dashboard).
    invalidateHelpdesk: () => {
      qc.invalidateQueries({ queryKey: ["helpdesk", ws] });
    },
  };
}

/** Ensure the TKT- number sequence exists (admin). */
export function useEnsureSetup() {
  return useMutation({ mutationFn: () => helpdeskApi.setup() });
}

/** Create a TKT-numbered ticket (or any helpdesk document); refreshes the generic helpdesk screens. */
export function useCreateDocument() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ entitySlug, data }: { entitySlug: HelpdeskEntitySlug; data: Record<string, unknown> }) =>
      helpdeskApi.createDocument(entitySlug, data),
    onSuccess: invalidateRecords,
  });
}

// ── ticket lifecycle ───────────────────────────────────────────────────────────────

/** Assign a ticket to an agent and/or team. */
export function useAssignTicket() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ recordId, agent, team }: { recordId: string; agent?: string; team?: string }) =>
      helpdeskApi.assignTicket(recordId, { agent, team }),
    onSuccess: invalidateRecords,
  });
}

/** Auto-assign a ticket via a chosen strategy. */
export function useAutoAssignTicket() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({
      recordId,
      method,
      team,
      skill,
    }: {
      recordId: string;
      method: AutoAssignMethod;
      team?: string;
      skill?: string;
    }) => helpdeskApi.autoAssignTicket(recordId, { method, team, skill }),
    onSuccess: invalidateRecords,
  });
}

/** Bump a ticket's escalation level. */
export function useEscalateTicket() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => helpdeskApi.escalateTicket(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Change a ticket's status (pauses/resumes SLA on waiting states). */
export function useSetTicketStatus() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ recordId, status }: { recordId: string; status: string }) =>
      helpdeskApi.setTicketStatus(recordId, status),
    onSuccess: invalidateRecords,
  });
}

/** Resolve a ticket (marks SLA met). */
export function useResolveTicket() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => helpdeskApi.resolveTicket(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Close a ticket. */
export function useCloseTicket() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => helpdeskApi.closeTicket(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Submit a CSAT response for a ticket. */
export function useSubmitCsat() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({
      recordId,
      rating,
      feedback,
      comments,
    }: {
      recordId: string;
      rating: number;
      feedback?: string;
      comments?: string;
    }) => helpdeskApi.submitCsat(recordId, { rating, feedback, comments }),
    onSuccess: invalidateRecords,
  });
}

/** Approve an ITSM change (admin). */
export function useApproveChange() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => helpdeskApi.approveChange(recordId),
    onSuccess: invalidateRecords,
  });
}

// ── native read panels ───────────────────────────────────────────────────────────

/** Deterministic knowledge recommendation (keyword/category match — NO AI). */
export function useKnowledgeRecommend(params: { category?: string; q?: string }, active: boolean) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["helpdesk", ws, "knowledge", params.category ?? "", params.q ?? ""],
    queryFn: () => helpdeskApi.recommendKnowledge(params),
    enabled: enabled && active,
    staleTime: 30_000,
  });
}

/** Workspace SLA health (breached/warning/on_track/met/paused). */
export function useSlaDashboard() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["helpdesk", ws, "sla-dashboard"],
    queryFn: () => helpdeskApi.slaDashboard(),
    enabled,
    staleTime: 15_000,
  });
}
