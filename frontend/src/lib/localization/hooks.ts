"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type EntityLabelWrite, localizationApi, type WorkspaceLocaleWrite } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, invalidate: () => qc.invalidateQueries({ queryKey: ["localization", ws] }) };
}

export function useLocale() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["localization", ws, "locale"], queryFn: () => localizationApi.getLocale(), enabled, staleTime: 60_000 });
}
export function useSetLocale() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: WorkspaceLocaleWrite) => localizationApi.setLocale(d), onSuccess: invalidate });
}

export function useEntityLabels() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["localization", ws, "entity-labels"], queryFn: () => localizationApi.listEntityLabels(), enabled, staleTime: 60_000 });
}
export function useCreateEntityLabel() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (d: EntityLabelWrite) => localizationApi.createEntityLabel(d), onSuccess: invalidate });
}
export function useDeleteEntityLabel() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => localizationApi.deleteEntityLabel(id), onSuccess: invalidate });
}
