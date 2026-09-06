"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  type PayPeriod,
  type PayrollSettings,
  type SalaryAssignment,
  type SalaryComponent,
  type SalaryStructure,
  payrollApi,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    qc,
    enabled: isReady && !!ws,
    /** Invalidate the whole payroll cache for this workspace. */
    invalidate: () => qc.invalidateQueries({ queryKey: ["payroll", ws] }),
  };
}

/** Whether the caller may run privileged payroll writes (server gates regardless). */
export function useCanManagePayroll(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

// ── settings + setup ────────────────────────────────────────────────────────
export function useSettings() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", ws, "settings"],
    queryFn: () => payrollApi.getSettings(),
    enabled,
    staleTime: 60_000,
  });
}
export function useUpdateSettings() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Partial<PayrollSettings>) => payrollApi.updateSettings(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "settings"] }),
  });
}
export function useRunSetup() {
  return useMutation({ mutationFn: () => payrollApi.setup() });
}

// ── salary structures + components ──────────────────────────────────────────
export function useStructures() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", ws, "structures"],
    queryFn: () => payrollApi.listStructures(),
    enabled,
    staleTime: 60_000,
  });
}
export function useStructure(id: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", ws, "structures", id],
    queryFn: () => payrollApi.getStructure(id as string),
    enabled: enabled && !!id,
  });
}
export function useCreateStructure() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Partial<SalaryStructure>) => payrollApi.createStructure(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "structures"] }),
  });
}
export function useUpdateStructure(id: string) {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Partial<SalaryStructure>) => payrollApi.updateStructure(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "structures"] }),
  });
}

export function useComponents(structureId: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", ws, "components", structureId],
    queryFn: () => payrollApi.listComponents(structureId as string),
    enabled: enabled && !!structureId,
  });
}
export function useCreateComponent(structureId: string) {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Partial<SalaryComponent>) => payrollApi.createComponent(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "components", structureId] }),
  });
}

// ── assignments / profiles / contracts ──────────────────────────────────────
export function useAssignments(employeeRecordId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", ws, "assignments", employeeRecordId ?? null],
    queryFn: () => payrollApi.listAssignments(employeeRecordId),
    enabled,
    staleTime: 30_000,
  });
}
export function useCreateAssignment() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Partial<SalaryAssignment>) => payrollApi.createAssignment(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "assignments"] }),
  });
}

// ── periods + lifecycle ─────────────────────────────────────────────────────
export function usePeriods() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", ws, "periods"],
    queryFn: () => payrollApi.listPeriods(),
    enabled,
    staleTime: 30_000,
  });
}
export function useCreatePeriod() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Partial<PayPeriod>) => payrollApi.createPeriod(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "periods"] }),
  });
}

/** A period lifecycle transition (open/close/lock/reopen) — invalidates periods + runs. */
function usePeriodTransition(fn: (id: string) => Promise<PayPeriod>) {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (id: string) => fn(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payroll", ws, "periods"] });
      qc.invalidateQueries({ queryKey: ["payroll", "runs", ws], exact: false });
    },
  });
}
export const useOpenPeriod = () => usePeriodTransition((id) => payrollApi.openPeriod(id));
export const useClosePeriod = () => usePeriodTransition((id) => payrollApi.closePeriod(id));
export const useLockPeriod = () => usePeriodTransition((id) => payrollApi.lockPeriod(id));
export const useReopenPeriod = () => usePeriodTransition((id) => payrollApi.reopenPeriod(id));

// ── runs + lifecycle ────────────────────────────────────────────────────────
export function useRuns(params?: { payroll_period_id?: string; status?: string }) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", "runs", ws, params ?? {}],
    queryFn: () => payrollApi.listRuns(params),
    enabled,
    staleTime: 15_000,
  });
}
export function useRun(id: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", "runs", ws, "detail", id],
    queryFn: () => payrollApi.getRun(id as string),
    enabled: enabled && !!id,
  });
}
export function useCreateRun() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (payrollPeriodId: string) => payrollApi.createRun(payrollPeriodId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", "runs", ws], exact: false }),
  });
}

/** A run lifecycle transition — invalidates runs + payslips (calculate/post change payslips). */
function useRunTransition(fn: (id: string) => Promise<unknown>) {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (id: string) => fn(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["payroll", "runs", ws], exact: false });
      qc.invalidateQueries({ queryKey: ["payroll", "payslips", ws], exact: false });
    },
  });
}
export const useCalculateRun = () => useRunTransition((id) => payrollApi.calculateRun(id));
export const useApproveRun = () => useRunTransition((id) => payrollApi.approveRun(id));
export const usePostRun = () => useRunTransition((id) => payrollApi.postRun(id));
export const useLockRun = () => useRunTransition((id) => payrollApi.lockRun(id));

export function useRunRegister(id: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", "runs", ws, "register", id],
    queryFn: () => payrollApi.runRegister(id as string),
    enabled: enabled && !!id,
  });
}
export function useRunSummary(id: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", "runs", ws, "summary", id],
    queryFn: () => payrollApi.runSummary(id as string),
    enabled: enabled && !!id,
  });
}

// ── payslips (read-only) ────────────────────────────────────────────────────
export function usePayslips(params?: { payroll_run_id?: string; employee_record_id?: string }) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", "payslips", ws, params ?? {}],
    queryFn: () => payrollApi.listPayslips(params),
    enabled,
    staleTime: 15_000,
  });
}
export function usePayslip(id: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["payroll", "payslips", ws, "detail", id],
    queryFn: () => payrollApi.getPayslip(id as string),
    enabled: enabled && !!id,
  });
}

// ── loans / advances / overtime / adjustments ───────────────────────────────
export function useLoans() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["payroll", ws, "loans"], queryFn: () => payrollApi.listLoans(), enabled, staleTime: 30_000 });
}
export function useCreateLoan() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => payrollApi.createLoan(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "loans"] }),
  });
}
export function useAdvances() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["payroll", ws, "advances"], queryFn: () => payrollApi.listAdvances(), enabled, staleTime: 30_000 });
}
export function useCreateAdvance() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => payrollApi.createAdvance(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "advances"] }),
  });
}
export function useOvertime() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["payroll", ws, "overtime"], queryFn: () => payrollApi.listOvertime(), enabled, staleTime: 30_000 });
}
export function useCreateOvertime() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => payrollApi.createOvertime(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "overtime"] }),
  });
}
export function useApproveOvertime() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (id: string) => payrollApi.approveOvertime(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "overtime"] }),
  });
}
export function useAdjustments() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["payroll", ws, "adjustments"], queryFn: () => payrollApi.listAdjustments(), enabled, staleTime: 30_000 });
}
export function useCreateAdjustment() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => payrollApi.createAdjustment(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payroll", ws, "adjustments"] }),
  });
}

// ── final settlement ────────────────────────────────────────────────────────
export function useCreateFinalSettlement() {
  return useMutation({ mutationFn: (data: Record<string, unknown>) => payrollApi.createFinalSettlement(data) });
}
