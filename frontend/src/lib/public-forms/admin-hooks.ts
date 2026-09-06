"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { publicFormsAdminApi } from "./admin-api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["public-forms-admin", ws] }) };
}

export function usePublicForms() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["public-forms-admin", ws, "forms"], queryFn: () => publicFormsAdminApi.listForms(), enabled, staleTime: 30_000 });
}
export function useUpdatePublicForm() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { is_public?: boolean; name?: string } }) => publicFormsAdminApi.updateForm(id, data),
    onSuccess: invalidate,
  });
}
export function useFormSubmissions(formId: string | null, status?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["public-forms-admin", ws, "submissions", formId, status ?? null],
    queryFn: () => publicFormsAdminApi.listSubmissions(formId!, status),
    enabled: enabled && !!formId,
    staleTime: 15_000,
  });
}
export function useApproveSubmission() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ formId, subId }: { formId: string; subId: string }) => publicFormsAdminApi.approve(formId, subId),
    onSuccess: invalidate,
  });
}
export function useRejectSubmission() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ formId, subId, reason }: { formId: string; subId: string; reason: string }) => publicFormsAdminApi.reject(formId, subId, reason),
    onSuccess: invalidate,
  });
}
