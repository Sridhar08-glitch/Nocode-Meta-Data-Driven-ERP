"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type DocumentTemplateWrite, documentTemplatesApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["document-templates", ws] }) };
}

export function useDocumentTemplates() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["document-templates", ws], queryFn: () => documentTemplatesApi.list(), enabled, staleTime: 60_000 });
}
export function useCreateDocTemplate() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: DocumentTemplateWrite) => documentTemplatesApi.create(d), onSuccess: invalidate });
}
export function useUpdateDocTemplate() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<DocumentTemplateWrite> }) => documentTemplatesApi.update(id, data),
    onSuccess: invalidate,
  });
}
export function useDeleteDocTemplate() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => documentTemplatesApi.remove(id), onSuccess: invalidate });
}
export function useRenderDocPdf() {
  return useMutation({
    mutationFn: ({ id, recordId, filename }: { id: string; recordId: string; filename: string }) =>
      documentTemplatesApi.renderPdf(id, recordId, filename),
  });
}
