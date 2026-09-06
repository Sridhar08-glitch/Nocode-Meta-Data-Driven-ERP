"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type AddMemberInput, type CreateWorkspaceInput, type WorkspaceDetail, workspaceAdminApi } from "./admin-api";

export type { WorkspaceMember } from "./admin-api";

/** Create a workspace (onboarding) — usable even when the user has no workspace yet. */
export function useCreateWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateWorkspaceInput) => workspaceAdminApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspaces"] }),
  });
}

function useWsScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, qc };
}

export function useWorkspaceDetail() {
  const { ws, enabled } = useWsScope();
  return useQuery({
    queryKey: ["workspace-detail", ws],
    queryFn: () => workspaceAdminApi.detail(ws as string),
    enabled,
    staleTime: 60_000,
  });
}

export function useUpdateWorkspace() {
  const { ws, qc } = useWsScope();
  return useMutation({
    mutationFn: (data: Partial<WorkspaceDetail>) => workspaceAdminApi.update(ws as string, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workspace-detail", ws] });
      qc.invalidateQueries({ queryKey: ["workspaces"] });
    },
  });
}

export function useMembers() {
  const { ws, enabled } = useWsScope();
  return useQuery({
    queryKey: ["workspace-members", ws],
    queryFn: () => workspaceAdminApi.members(ws as string),
    enabled,
    staleTime: 30_000,
  });
}

function useMemberMutation<T>(fn: (ws: string) => (arg: T) => Promise<unknown>) {
  const { ws, qc } = useWsScope();
  return useMutation({
    mutationFn: (arg: T) => fn(ws as string)(arg),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspace-members", ws] }),
  });
}

export function useAddMember() {
  const { ws, qc } = useWsScope();
  return useMutation({
    mutationFn: (data: AddMemberInput) => workspaceAdminApi.addMember(ws as string, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspace-members", ws] }),
  });
}
export function useAssignRole() {
  return useMemberMutation<{ memberId: string; role: string }>(
    (ws) => ({ memberId, role }) => workspaceAdminApi.assignRole(ws, memberId, role));
}
export function useRemoveMember() {
  return useMemberMutation<string>((ws) => (memberId) => workspaceAdminApi.removeMember(ws, memberId));
}
export function useSuspendMember() {
  return useMemberMutation<string>((ws) => (memberId) => workspaceAdminApi.suspendMember(ws, memberId));
}
export function useReactivateMember() {
  return useMemberMutation<string>((ws) => (memberId) => workspaceAdminApi.reactivateMember(ws, memberId));
}
export function useResetMemberPassword() {
  const { ws } = useWsScope();
  return useMutation({ mutationFn: (memberId: string) => workspaceAdminApi.resetPassword(ws as string, memberId) });
}
export function useTransferOwnership() {
  return useMemberMutation<string>((ws) => (memberId) => workspaceAdminApi.transferOwnership(ws, memberId));
}

// ── invitation lifecycle ─────────────────────────────────────────────────────
export function useInvitations(status?: string) {
  const { ws, enabled } = useWsScope();
  return useQuery({
    queryKey: ["workspace-invitations", ws, status ?? "all"],
    queryFn: () => workspaceAdminApi.invitations(ws as string, status),
    enabled,
    staleTime: 30_000,
  });
}

function useInvitationMutation<T>(fn: (ws: string) => (arg: T) => Promise<unknown>) {
  const { ws, qc } = useWsScope();
  return useMutation({
    mutationFn: (arg: T) => fn(ws as string)(arg),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspace-invitations", ws] }),
  });
}

export function useInvite() {
  return useInvitationMutation<{ email: string; role?: string }>(
    (ws) => (data) => workspaceAdminApi.invite(ws, data));
}
export function useResendInvitation() {
  return useInvitationMutation<string>((ws) => (id) => workspaceAdminApi.resendInvitation(ws, id));
}
export function useCancelInvitation() {
  return useInvitationMutation<string>((ws) => (id) => workspaceAdminApi.cancelInvitation(ws, id));
}

export function useAcceptInvitation() {
  return useMutation({ mutationFn: (token: string) => workspaceAdminApi.acceptInvitation(token) });
}
export function useRejectInvitation() {
  return useMutation({ mutationFn: (token: string) => workspaceAdminApi.rejectInvitation(token) });
}

// ── workspace lifecycle ──────────────────────────────────────────────────────
export function useArchivedWorkspaces() {
  const qc = useQueryClient();
  return {
    query: useQuery({ queryKey: ["archived-workspaces"], queryFn: workspaceAdminApi.archivedWorkspaces }),
    refresh: () => {
      qc.invalidateQueries({ queryKey: ["archived-workspaces"] });
      qc.invalidateQueries({ queryKey: ["workspaces"] });
    },
  };
}
export function useArchiveWorkspace() {
  const { ws, qc } = useWsScope();
  return useMutation({
    mutationFn: () => workspaceAdminApi.archiveWorkspace(ws as string),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspaces"] }),
  });
}
export function useSoftDeleteWorkspace() {
  const { ws, qc } = useWsScope();
  return useMutation({
    mutationFn: () => workspaceAdminApi.softDeleteWorkspace(ws as string),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspaces"] }),
  });
}
export function useRequestHardDelete() {
  const { ws } = useWsScope();
  return useMutation({ mutationFn: () => workspaceAdminApi.requestHardDelete(ws as string) });
}
export function useConfirmHardDelete() {
  const { ws, qc } = useWsScope();
  return useMutation({
    mutationFn: (token: string) => workspaceAdminApi.confirmHardDelete(ws as string, token),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workspaces"] }),
  });
}
export function useRestoreWorkspace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => workspaceAdminApi.restoreWorkspace(slug),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["archived-workspaces"] });
      qc.invalidateQueries({ queryKey: ["workspaces"] });
    },
  });
}
