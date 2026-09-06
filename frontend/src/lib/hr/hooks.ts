"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type HrEntitySlug, hrApi } from "./api";

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

/** Ensure the CAN / INT / OFF / EMP number sequences exist (admin). */
export function useEnsureSetup() {
  return useMutation({ mutationFn: () => hrApi.setup() });
}

/** Create an HR document; candidate/interview/offer/employee get a gapless `number` allocated server-side. */
export function useCreateDocument() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ entitySlug, data }: { entitySlug: HrEntitySlug; data: Record<string, unknown> }) =>
      hrApi.createDocument(entitySlug, data),
    onSuccess: invalidateRecords,
  });
}

/** Hire a candidate (status→hired) and create a linked, EMP-numbered Employee. */
export function useHireCandidate() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => hrApi.hireCandidate(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Mark an interview completed (status→completed). */
export function useCompleteInterview() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => hrApi.completeInterview(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Mark an offer accepted (status→accepted). */
export function useAcceptOffer() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => hrApi.acceptOffer(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Approve a leave request (status→approved + decrements the linked leave balance). */
export function useApproveLeave() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => hrApi.approveLeave(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Reject a leave request (status→rejected). */
export function useRejectLeave() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => hrApi.rejectLeave(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Mark a performance review completed (status→completed). */
export function useCompletePerformance() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => hrApi.completePerformance(recordId),
    onSuccess: invalidateRecords,
  });
}

/** Promote an employee to a new position (id + new_position record id). */
export function usePromoteEmployee() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ recordId, newPosition }: { recordId: string; newPosition: string }) =>
      hrApi.promoteEmployee(recordId, newPosition),
    onSuccess: invalidateRecords,
  });
}

/** Transfer an employee to a new department (id + new_department record id). */
export function useTransferEmployee() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: ({ recordId, newDepartment }: { recordId: string; newDepartment: string }) =>
      hrApi.transferEmployee(recordId, newDepartment),
    onSuccess: invalidateRecords,
  });
}

/** Offboard an employee (status→terminated). */
export function useOffboardEmployee() {
  const { invalidateRecords } = useScope();
  return useMutation({
    mutationFn: (recordId: string) => hrApi.offboardEmployee(recordId),
    onSuccess: invalidateRecords,
  });
}
