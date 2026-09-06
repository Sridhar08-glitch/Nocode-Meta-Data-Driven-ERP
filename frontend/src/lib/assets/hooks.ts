"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  type DepreciationMethod,
  type DisposalMethod,
  assetsApi,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    // A lifecycle / depreciation / disposal action mutates the underlying generic asset records;
    // refresh the F1.7 record caches (keyed ["data", ws, <entity>]) + the entity list so the
    // generic `/e/<entity>` screens update.
    invalidateRecords: () => {
      qc.invalidateQueries({ queryKey: ["data", ws] });
      qc.invalidateQueries({ queryKey: ["entities", ws] });
    },
    // Refresh the native depreciation/disposal lists.
    invalidateAssets: () => {
      qc.invalidateQueries({ queryKey: ["assets", ws] });
    },
  };
}

/** Ensure the AST number sequence exists (admin). */
export function useEnsureSetup() {
  return useMutation({ mutationFn: () => assetsApi.setup() });
}

/** Create an AST-numbered asset (refreshes the generic asset screens). */
export function useCreateAsset() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => assetsApi.createAsset(data),
    onSuccess: invalidateRecords,
  });
}

/** Assign an asset to an employee / department / team. */
export function useAssignAsset() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({
      recordId,
      data,
    }: {
      recordId: string;
      data: { employee?: string; department?: string; team?: string };
    }) => assetsApi.assignAsset(recordId, data),
    onSuccess: invalidateRecords,
  });
}

/** Return an assigned asset (status→in_service). */
export function useReturnAsset() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => assetsApi.returnAsset(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Transfer an asset between locations / holders. */
export function useTransferAsset() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({
      recordId,
      data,
    }: {
      recordId: string;
      data: { transfer_type: string; from_ref: string; to_ref: string };
    }) => assetsApi.transferAsset(recordId, data),
    onSuccess: invalidateRecords,
  });
}

/** Record an inspection result against an asset. */
export function useInspectAsset() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({
      recordId,
      data,
    }: {
      recordId: string;
      data: { result: "passed" | "failed" | "requires_attention"; notes: string };
    }) => assetsApi.inspectAsset(recordId, data),
    onSuccess: invalidateRecords,
  });
}

/** Retire an asset (admin) — produces a disposal/retirement record. */
export function useRetireAsset() {
  const { invalidateRecords, invalidateAssets } = useScope();
  return useMutation({
    mutationFn: ({
      recordId,
      data,
    }: {
      recordId: string;
      data: { reason: string; residual_value: string };
    }) => assetsApi.retireAsset(recordId, data),
    onSuccess: () => {
      invalidateRecords();
      invalidateAssets();
    },
  });
}

/** Mark a maintenance work order completed. */
export function useCompleteWorkOrder() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => assetsApi.completeWorkOrder(recordId),
    onSuccess: invalidateRecords,
  });
}

// ── native depreciation engine ─────────────────────────────────────────────────

/** Depreciation schedules, optionally filtered by asset. */
export function useSchedules(assetRecordId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["assets", ws, "schedules", assetRecordId ?? null],
    queryFn: () => assetsApi.listSchedules(assetRecordId),
    enabled,
    staleTime: 30_000,
  });
}

export function useCreateSchedule() {
  const { invalidateAssets } = useScope();
  return useMutation({
    mutationFn: (data: {
      asset_record_id: string;
      method: DepreciationMethod;
      acquisition_cost: string;
      salvage_value: string;
      useful_life_months: number;
      start_date: string;
    }) => assetsApi.createSchedule(data),
    onSuccess: invalidateAssets,
  });
}

/** Post the next immutable depreciation entry for one schedule. */
export function useRunDepreciation() {
  const { invalidateAssets } = useScope();
  return useMutation({
    mutationFn: ({ scheduleId, periodDate }: { scheduleId: string; periodDate: string }) =>
      assetsApi.runDepreciation(scheduleId, periodDate),
    onSuccess: invalidateAssets,
  });
}

/** Post the next entry for every active schedule (admin). */
export function useRunAllDepreciation() {
  const { invalidateAssets } = useScope();
  return useMutation({
    mutationFn: (periodDate: string) => assetsApi.runAllDepreciation(periodDate),
    onSuccess: invalidateAssets,
  });
}

/** Entries already posted against a schedule. */
export function useScheduleEntries(scheduleId: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["assets", ws, "schedule-entries", scheduleId],
    queryFn: () => assetsApi.scheduleEntries(scheduleId!),
    enabled: enabled && !!scheduleId,
    staleTime: 15_000,
  });
}

/** Compute a full schedule without writing anything (preview aid). */
export function useDepreciationPreview() {
  return useMutation({
    mutationFn: (data: {
      method: DepreciationMethod;
      acquisition_cost: string;
      salvage_value: string;
      useful_life_months: number;
    }) => assetsApi.previewDepreciation(data),
  });
}

// ── native disposal engine ─────────────────────────────────────────────────────

/** Disposals, optionally filtered by asset. */
export function useDisposals(assetRecordId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["assets", ws, "disposals", assetRecordId ?? null],
    queryFn: () => assetsApi.listDisposals(assetRecordId),
    enabled,
    staleTime: 30_000,
  });
}

export function useCreateDisposal() {
  const { invalidateRecords, invalidateAssets } = useScope();
  return useMutation({
    mutationFn: (data: {
      asset_record_id: string;
      method: DisposalMethod;
      proceeds: string;
      book_value?: string;
      reason: string;
    }) => assetsApi.createDisposal(data),
    onSuccess: () => {
      invalidateRecords();
      invalidateAssets();
    },
  });
}
