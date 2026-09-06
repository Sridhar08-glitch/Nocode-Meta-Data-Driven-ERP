"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type TagCreate, tagsApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, qc };
}

export function useTags() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["tags", ws, "list"], queryFn: () => tagsApi.list(), enabled, staleTime: 60_000 });
}
export function useCreateTag() {
  const { ws, enabled, qc } = useScope();
  void enabled;
  return useMutation({ mutationFn: (d: TagCreate) => tagsApi.create(d), onSuccess: () => qc.invalidateQueries({ queryKey: ["tags", ws] }) });
}
export function useRecordTags(recordId: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["tags", ws, "record", recordId],
    queryFn: () => tagsApi.forRecord(recordId),
    enabled: enabled && !!recordId,
    staleTime: 30_000,
  });
}
export function useAttachTag(entitySlug: string, recordId: string) {
  const { ws, qc } = useScope();
  return useMutation({
    mutationFn: (tagId: string) => tagsApi.attach(entitySlug, tagId, recordId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tags", ws, "record", recordId] }),
  });
}
export function useDetachTag(recordId: string) {
  const { ws, qc } = useScope();
  return useMutation({
    mutationFn: (tagId: string) => tagsApi.detach(tagId, recordId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tags", ws, "record", recordId] }),
  });
}
