"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  permissionsApi,
  type FieldPermissionWrite,
  type MaskingRuleWrite,
  type PermissionWrite,
  type RoleWrite,
} from "./api";

/** Workspace-scoped cache for the permission model; mutations invalidate the whole root. */
function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => qc.invalidateQueries({ queryKey: ["permissions", ws] }),
  };
}

const STALE = 60_000;

// ── roles ─────────────────────────────────────────────────────────────────────────
export function useRoles() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["permissions", ws, "roles"],
    queryFn: () => permissionsApi.listRoles(),
    enabled,
    staleTime: STALE,
  });
}

export function useCreateRole() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: RoleWrite) => permissionsApi.createRole(data), onSuccess: invalidate });
}
export function useUpdateRole() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<RoleWrite> }) =>
      permissionsApi.updateRole(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteRole() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => permissionsApi.deleteRole(id), onSuccess: invalidate });
}

// ── permission grants (optionally filtered by role) ─────────────────────────────────
export function usePermissions(roleId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["permissions", ws, "grants", roleId ?? "all"],
    queryFn: () => permissionsApi.listPermissions(roleId),
    enabled,
    staleTime: STALE,
  });
}

export function useCreatePermission() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (data: PermissionWrite) => permissionsApi.createPermission(data),
    onSuccess: invalidate,
  });
}
export function useUpdatePermission() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<PermissionWrite> }) =>
      permissionsApi.updatePermission(id, data),
    onSuccess: invalidate,
  });
}
export function useDeletePermission() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (id: string) => permissionsApi.deletePermission(id),
    onSuccess: invalidate,
  });
}

// ── field permissions ───────────────────────────────────────────────────────────────
export function useFieldPermissions(roleId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["permissions", ws, "field-permissions", roleId ?? "all"],
    queryFn: () => permissionsApi.listFieldPermissions(roleId),
    enabled,
    staleTime: STALE,
  });
}
export function useCreateFieldPermission() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (data: FieldPermissionWrite) => permissionsApi.createFieldPermission(data),
    onSuccess: invalidate,
  });
}
export function useUpdateFieldPermission() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<FieldPermissionWrite> }) =>
      permissionsApi.updateFieldPermission(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteFieldPermission() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (id: string) => permissionsApi.deleteFieldPermission(id),
    onSuccess: invalidate,
  });
}

// ── masking rules ─────────────────────────────────────────────────────────────────
export function useMaskingRules(roleId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["permissions", ws, "masking-rules", roleId ?? "all"],
    queryFn: () => permissionsApi.listMaskingRules(roleId),
    enabled,
    staleTime: STALE,
  });
}
export function useCreateMaskingRule() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (data: MaskingRuleWrite) => permissionsApi.createMaskingRule(data),
    onSuccess: invalidate,
  });
}
export function useUpdateMaskingRule() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<MaskingRuleWrite> }) =>
      permissionsApi.updateMaskingRule(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteMaskingRule() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: (id: string) => permissionsApi.deleteMaskingRule(id),
    onSuccess: invalidate,
  });
}
