"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type EmailTemplateWrite, emailTemplatesApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["email-templates", ws] }) };
}

export function useEmailTemplates() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["email-templates", ws], queryFn: () => emailTemplatesApi.list(), enabled, staleTime: 60_000 });
}
export function useCreateEmailTemplate() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: EmailTemplateWrite) => emailTemplatesApi.create(d), onSuccess: invalidate });
}
export function useUpdateEmailTemplate() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<EmailTemplateWrite> }) => emailTemplatesApi.update(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteEmailTemplate() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => emailTemplatesApi.remove(id), onSuccess: invalidate });
}
export function useRenderEmailTemplate() {
  return useMutation({ mutationFn: ({ id, context }: { id: string; context?: Record<string, unknown> }) => emailTemplatesApi.render(id, context) });
}
export function useTestSendEmailTemplate() {
  return useMutation({
    mutationFn: ({ id, toEmail, context }: { id: string; toEmail: string; context?: Record<string, unknown> }) => emailTemplatesApi.testSend(id, toEmail, context),
  });
}
