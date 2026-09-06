"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type ProcurementEntitySlug, procurementApi } from "./api";

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
    // Posting a goods receipt writes the Inventory ledger — refresh inventory balances too.
    invalidateInventory: () => {
      qc.invalidateQueries({ queryKey: ["inventory", ws] });
    },
  };
}

/** Ensure the RFQ/PO/GR/VB number sequences exist (admin). */
export function useEnsureSetup() {
  return useMutation({ mutationFn: () => procurementApi.setup() });
}

/** Create a procurement document; numbered docs get a gapless `number` allocated server-side. */
export function useCreateDocument() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ entitySlug, data }: { entitySlug: ProcurementEntitySlug; data: Record<string, unknown> }) =>
      procurementApi.createDocument(entitySlug, data),
    onSuccess: invalidateRecords,
  });
}

/** Approve a procurement document (RFQ / PO / vendor bill). */
export function useApproveDocument() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ entitySlug, recordId }: { entitySlug: ProcurementEntitySlug; recordId: string }) =>
      procurementApi.approveDocument(entitySlug, recordId),
    onSuccess: invalidateRecords,
  });
}

/** Post a goods receipt into the Inventory ledger (increases stock). */
export function usePostGoodsReceipt() {
  const { invalidateRecords, invalidateInventory } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => procurementApi.postGoodsReceipt(recordId),
    onSuccess: () => {
      invalidateRecords();
      invalidateInventory();
    },
  });
}

/** Post a vendor bill (emits a GL event). */
export function usePostVendorBill() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => procurementApi.postVendorBill(recordId),
    onSuccess: invalidateRecords,
  });
}
