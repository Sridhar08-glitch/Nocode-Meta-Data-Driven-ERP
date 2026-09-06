"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type DocListParams, documentsApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["documents", ws] }) };
}

export function useFolders() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["documents", ws, "folders"], queryFn: () => documentsApi.listFolders(), enabled, staleTime: 60_000 });
}
export function useCreateFolder() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: { name: string; parent_id?: string | null }) => documentsApi.createFolder(d), onSuccess: invalidate });
}
export function useDeleteFolder() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => documentsApi.deleteFolder(id), onSuccess: invalidate });
}

export function useDocuments(params: DocListParams = {}) {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["documents", ws, "list", params], queryFn: () => documentsApi.list(params), enabled, staleTime: 30_000 });
}
export function useUploadDocument() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (form: FormData) => documentsApi.upload(form), onSuccess: invalidate });
}
export function useDeleteDocument() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => documentsApi.remove(id), onSuccess: invalidate });
}
export function useDocumentVersions(id: string | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["documents", ws, "versions", id],
    queryFn: () => documentsApi.versions(id!),
    enabled: enabled && !!id,
    staleTime: 30_000,
  });
}
export function useUploadVersion() {
  const { invalidate } = useScope();
  return useMutation({
    mutationFn: ({ id, form }: { id: string; form: FormData }) => documentsApi.uploadVersion(id, form),
    onSuccess: invalidate,
  });
}
