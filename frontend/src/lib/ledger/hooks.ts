"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  type AccountingPeriod,
  type AccountType,
  type EntryStatus,
  type JournalEntryWrite,
  type LedgerAccount,
  ledgerApi,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => qc.invalidateQueries({ queryKey: ["ledger", ws] }),
  };
}

export function useLedgerAccounts(type?: AccountType) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["ledger", ws, "accounts", type ?? "all"],
    queryFn: () => ledgerApi.listAccounts(type),
    enabled,
    staleTime: 60_000,
  });
}
export function useCreateAccount() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: Partial<LedgerAccount>) => ledgerApi.createAccount(data), onSuccess: invalidate });
}
export function useDeleteAccount() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => ledgerApi.deleteAccount(id), onSuccess: invalidate });
}

export function useJournalEntries(params?: { status?: EntryStatus; source_module?: string }) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["ledger", ws, "entries", params ?? {}],
    queryFn: () => ledgerApi.listEntries(params),
    enabled,
    staleTime: 15_000,
  });
}
export function useCreateEntry() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: JournalEntryWrite) => ledgerApi.createEntry(data), onSuccess: invalidate });
}
export function usePostEntry() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => ledgerApi.postEntry(id), onSuccess: invalidate });
}
export function useReverseEntry() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => ledgerApi.reverseEntry(id), onSuccess: invalidate });
}
export function useDeleteEntry() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => ledgerApi.deleteEntry(id), onSuccess: invalidate });
}

export function usePeriods() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["ledger", ws, "periods"],
    queryFn: () => ledgerApi.listPeriods(),
    enabled,
    staleTime: 60_000,
  });
}
export function useCreatePeriod() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: Partial<AccountingPeriod>) => ledgerApi.createPeriod(data), onSuccess: invalidate });
}
export function useClosePeriod() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, lock }: { id: string; lock?: boolean }) => ledgerApi.closePeriod(id, lock),
    onSuccess: invalidate,
  });
}
export function useReopenPeriod() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => ledgerApi.reopenPeriod(id), onSuccess: invalidate });
}

// ── setup + reports (P2.3) ────────────────────────────────────────────────────
export function useSeedChart() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: () => ledgerApi.seedChart(), onSuccess: invalidate });
}
export function useGenerateFiscalYear() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ year, startMonth }: { year: number; startMonth?: number }) =>
      ledgerApi.generateFiscalYear(year, startMonth ?? 1),
    onSuccess: invalidate,
  });
}
export function useTrialBalance(asOf?: string) {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["ledger", ws, "trial-balance", asOf ?? null], queryFn: () => ledgerApi.trialBalance(asOf), enabled });
}
export function useProfitLoss(from?: string, to?: string) {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["ledger", ws, "pl", from ?? null, to ?? null], queryFn: () => ledgerApi.profitLoss(from, to), enabled });
}
export function useBalanceSheet(asOf?: string) {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["ledger", ws, "bs", asOf ?? null], queryFn: () => ledgerApi.balanceSheet(asOf), enabled });
}
export function useGeneralLedger(accountId: string | null, from?: string, to?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["ledger", ws, "gl", accountId, from ?? null, to ?? null],
    queryFn: () => ledgerApi.generalLedger(accountId!, from, to),
    enabled: enabled && !!accountId,
  });
}
