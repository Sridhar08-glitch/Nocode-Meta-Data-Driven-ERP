"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { approvalsApi, type ApprovalProcessWrite } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["approvals", ws] }) };
}

export function useApprovalProcesses() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["approvals", ws, "processes"],
    queryFn: () => approvalsApi.listProcesses(),
    enabled,
    staleTime: 30_000,
  });
}
export function useCreateProcess() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: ApprovalProcessWrite) => approvalsApi.createProcess(d), onSuccess: invalidate });
}
export function useUpdateProcess() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ApprovalProcessWrite> }) => approvalsApi.updateProcess(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteProcess() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => approvalsApi.deleteProcess(id), onSuccess: invalidate });
}

export function usePendingApprovals() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["approvals", ws, "pending"],
    queryFn: () => approvalsApi.pendingForMe(),
    enabled,
    staleTime: 15_000,
  });
}
export function useApproveRequest() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) => approvalsApi.approve(id, comment),
    onSuccess: invalidate,
  });
}
export function useRejectRequest() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) => approvalsApi.reject(id, comment),
    onSuccess: invalidate,
  });
}
