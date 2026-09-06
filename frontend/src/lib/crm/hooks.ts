"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type CrmEntitySlug, crmApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    // A lifecycle action mutates the underlying generic records; refresh the F1.7 record
    // caches (keyed ["data", ws, <entity>]) + the entity list so the generic screens update.
    invalidateRecords: () => {
      qc.invalidateQueries({ queryKey: ["data", ws] });
      qc.invalidateQueries({ queryKey: ["entities", ws] });
    },
  };
}

/** Ensure the LEAD / ACC / OPP number sequences exist (admin). */
export function useEnsureSetup() {
  return useMutation({ mutationFn: () => crmApi.setup() });
}

/** Create a CRM document; lead/account/opportunity get a gapless `number` allocated server-side. */
export function useCreateDocument() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ entitySlug, data }: { entitySlug: CrmEntitySlug; data: Record<string, unknown> }) =>
      crmApi.createDocument(entitySlug, data),
    onSuccess: invalidateRecords,
  });
}

/** Qualify a lead (status→qualified) and create a linked, numbered Opportunity. */
export function useQualifyLead() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => crmApi.qualifyLead(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Mark an opportunity won (stage→won + close reason). */
export function useWinOpportunity() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ recordId, reason }: { recordId: string; reason: string }) =>
      crmApi.winOpportunity(recordId, reason),
    onSuccess: invalidateRecords,
  });
}

/** Mark an opportunity lost (stage→lost + close reason). */
export function useLoseOpportunity() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ recordId, reason }: { recordId: string; reason: string }) =>
      crmApi.loseOpportunity(recordId, reason),
    onSuccess: invalidateRecords,
  });
}

/** Mark an activity completed (status→completed). */
export function useCompleteActivity() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => crmApi.completeActivity(recordId),
    onSuccess: invalidateRecords,
  });
}
