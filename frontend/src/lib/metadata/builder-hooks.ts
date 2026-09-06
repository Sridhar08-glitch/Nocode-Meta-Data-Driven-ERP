"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { builderApi } from "./builder-api";
import type {
  EntityCreate,
  EntityUpdate,
  FieldCreate,
  FieldUpdate,
  FormCreate,
  FormUpdate,
  ModuleWrite,
} from "./types";

/** Workspace-scoped metadata cache root; mutations invalidate it so nav/forms/lists refresh. */
function useMetaScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["meta", ws] });
  return { ws, enabled: isReady && !!ws, invalidate };
}

// ── queries ────────────────────────────────────────────────────────────────────
export function useFields(entity: string) {
  const { ws, enabled } = useMetaScope();
  return useQuery({
    queryKey: ["meta", ws, "fields", entity],
    queryFn: () => builderApi.listFields(entity),
    enabled: enabled && !!entity,
    staleTime: 60_000,
  });
}

export function useForms(entity: string) {
  const { ws, enabled } = useMetaScope();
  return useQuery({
    queryKey: ["meta", ws, "forms", entity],
    queryFn: () => builderApi.listForms(entity),
    enabled: enabled && !!entity,
    staleTime: 60_000,
  });
}

export function useForm(entity: string, formId: string) {
  const { ws, enabled } = useMetaScope();
  return useQuery({
    queryKey: ["meta", ws, "form", entity, formId],
    queryFn: () => builderApi.getForm(entity, formId),
    enabled: enabled && !!entity && !!formId,
  });
}

export function useSchemaVersions(entity: string) {
  const { ws, enabled } = useMetaScope();
  return useQuery({
    queryKey: ["meta", ws, "schema-versions", entity],
    queryFn: () => builderApi.schemaVersions(entity),
    enabled: enabled && !!entity,
  });
}

// ── entity mutations ─────────────────────────────────────────────────────────────
export function useCreateEntity() {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: (data: EntityCreate) => builderApi.createEntity(data),
    onSuccess: invalidate,
  });
}

export function useUpdateEntity(slug: string) {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: (data: EntityUpdate) => builderApi.updateEntity(slug, data),
    onSuccess: invalidate,
  });
}

export function useDeleteEntity() {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: (slug: string) => builderApi.deleteEntity(slug),
    onSuccess: invalidate,
  });
}

// ── field mutations ──────────────────────────────────────────────────────────────
export function useCreateField(entity: string) {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: (data: FieldCreate) => builderApi.createField(entity, data),
    onSuccess: invalidate,
  });
}

export function useUpdateField(entity: string) {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: ({ fieldSlug, data }: { fieldSlug: string; data: FieldUpdate }) =>
      builderApi.updateField(entity, fieldSlug, data),
    onSuccess: invalidate,
  });
}

export function useDeleteField(entity: string) {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: (fieldSlug: string) => builderApi.deleteField(entity, fieldSlug),
    onSuccess: invalidate,
  });
}

export function usePromoteField(entity: string) {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: ({ fieldSlug, promote }: { fieldSlug: string; promote: boolean }) =>
      promote
        ? builderApi.promoteField(entity, fieldSlug)
        : builderApi.demoteField(entity, fieldSlug),
    onSuccess: invalidate,
  });
}

// ── form mutations ───────────────────────────────────────────────────────────────
export function useCreateForm(entity: string) {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: (data: FormCreate) => builderApi.createForm(entity, data),
    onSuccess: invalidate,
  });
}

export function useUpdateForm(entity: string) {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: ({ formId, data }: { formId: string; data: FormUpdate }) =>
      builderApi.updateForm(entity, formId, data),
    onSuccess: invalidate,
  });
}

export function useDeleteForm(entity: string) {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: (formId: string) => builderApi.deleteForm(entity, formId),
    onSuccess: invalidate,
  });
}

// ── module + schema rollback ─────────────────────────────────────────────────────
export function useCreateModule() {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: (data: ModuleWrite) => builderApi.createModule(data),
    onSuccess: invalidate,
  });
}

export function useRollbackSchema(entity: string) {
  const { invalidate } = useMetaScope();
  return useMutation({
    mutationFn: (version: number) => builderApi.rollbackSchema(entity, version),
    onSuccess: invalidate,
  });
}
