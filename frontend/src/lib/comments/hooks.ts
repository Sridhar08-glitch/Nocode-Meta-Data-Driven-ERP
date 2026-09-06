"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type CommentCreate, commentsApi } from "./api";

function useScope(slug: string, recordId: string) {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  const key = ["comments", ws, slug, recordId];
  return { ws, enabled: isReady && !!ws && !!slug && !!recordId, key, invalidate: () => qc.invalidateQueries({ queryKey: key }) };
}

export function useComments(slug: string, recordId: string) {
  const { enabled, key } = useScope(slug, recordId);
  return useQuery({ queryKey: key, queryFn: () => commentsApi.list(slug, recordId), enabled, staleTime: 15_000 });
}
export function useCreateComment(slug: string, recordId: string) {
  const { invalidate } = useScope(slug, recordId);
  return useMutation({ mutationFn: (data: CommentCreate) => commentsApi.create(slug, recordId, data), onSuccess: invalidate });
}
export function useEditComment(slug: string, recordId: string) {
  const { invalidate } = useScope(slug, recordId);
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: string }) => commentsApi.edit(slug, recordId, id, body),
    onSuccess: invalidate,
  });
}
export function useDeleteComment(slug: string, recordId: string) {
  const { invalidate } = useScope(slug, recordId);
  return useMutation({ mutationFn: (id: string) => commentsApi.remove(slug, recordId, id), onSuccess: invalidate });
}
export function useTogglePin(slug: string, recordId: string) {
  const { invalidate } = useScope(slug, recordId);
  return useMutation({
    mutationFn: ({ id, pinned }: { id: string; pinned: boolean }) =>
      pinned ? commentsApi.unpin(slug, recordId, id) : commentsApi.pin(slug, recordId, id),
    onSuccess: invalidate,
  });
}
