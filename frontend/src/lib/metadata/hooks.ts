"use client";

import { useQuery } from "@tanstack/react-query";

import { descriptorToFormSchema } from "@/lib/system-entities/adapt";
import { systemEntitiesApi } from "@/lib/system-entities/api";
import {
  useSystemEntitiesAsMeta,
  useSystemEntityDescriptor,
} from "@/lib/system-entities/hooks";
import { useTenant } from "@/lib/tenant/context";

import { metadataApi } from "./api";
import type { EntityMeta } from "./types";

/** Metadata entities for the active workspace (cached by slug). Unchanged — feeds the Studio
 *  builder, which only edits metadata `EntityDefinition`s (never system entities). */
export function useEntities() {
  const { workspace, isReady } = useTenant();
  const slug = workspace?.slug ?? null;
  return useQuery({
    queryKey: ["meta", slug, "entities"],
    queryFn: metadataApi.entities,
    enabled: isReady && !!slug,
    staleTime: 5 * 60_000,
  });
}

/** The RUNTIME entity list = metadata entities (kind:"metadata") + system entities (kind:"system").
 *  This is what the sidebar nav + record runtime resolve against, so native-model engines render
 *  through the Generic Runtime exactly like metadata entities (B0.2). */
export function useRuntimeEntities(): { data: EntityMeta[]; isSuccess: boolean; isLoading: boolean } {
  const meta = useEntities();
  const system = useSystemEntitiesAsMeta();
  const data: EntityMeta[] = [
    ...(meta.data ?? []).map((e) => ({ ...e, kind: e.kind ?? ("metadata" as const) })),
    ...system.data,
  ];
  // Ready when metadata succeeded and the (optional) system list has SETTLED — a system-entities
  // failure must never block metadata entities.
  return { data, isSuccess: meta.isSuccess && system.settled, isLoading: meta.isLoading };
}

/** Source discriminator for a slug (from the cached runtime list). `undefined` until resolved. */
export function useEntityKind(slug: string): { kind?: "metadata" | "system"; ready: boolean } {
  const rt = useRuntimeEntities();
  const found = rt.data.find((e) => e.slug === slug);
  if (found) return { kind: found.kind ?? "metadata", ready: true };
  return { kind: rt.isSuccess ? "metadata" : undefined, ready: rt.isSuccess };
}

export function useModules() {
  const { workspace, isReady } = useTenant();
  const slug = workspace?.slug ?? null;
  return useQuery({
    queryKey: ["meta", slug, "modules"],
    queryFn: metadataApi.modules,
    enabled: isReady && !!slug,
    staleTime: 5 * 60_000,
  });
}

/** The active workspace's entity meta for one slug — SOURCE-AWARE (B0.2): metadata entities come
 *  from the cached list; system entities are fetched as a full descriptor and adapted to EntityMeta.
 *  Same return shape for both, so the runtime page is unchanged. */
export function useEntityMeta(slug: string) {
  const { kind } = useEntityKind(slug);
  const isSystem = kind === "system";
  const query = useEntities();
  const sys = useSystemEntityDescriptor(slug, isSystem);
  if (isSystem) {
    return {
      entity: sys.data ?? null,
      isLoading: sys.isLoading,
      isError: sys.isError,
      query: sys,
    };
  }
  const entity = query.data?.find((e) => e.slug === slug) ?? null;
  return { entity, isLoading: query.isLoading, isError: query.isError, query };
}

/** Resolved FormSchema for one entity (record create/edit forms, F1.6) — SOURCE-AWARE (B0.2):
 *  system entities derive their FormSchema from the B0 descriptor (writable fields). */
export function useFormSchema(entitySlug: string) {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const { kind } = useEntityKind(entitySlug);
  const isSystem = kind === "system";
  const metaQuery = useQuery({
    queryKey: ["meta", ws, "form-schema", entitySlug],
    queryFn: () => metadataApi.formSchema(entitySlug),
    enabled: isReady && !!ws && !!entitySlug && kind === "metadata",
    staleTime: 5 * 60_000,
  });
  const sysQuery = useQuery({
    queryKey: ["sysent", ws, "form-schema", entitySlug],
    queryFn: () =>
      systemEntitiesApi.descriptor(entitySlug).then(descriptorToFormSchema),
    enabled: isReady && !!ws && !!entitySlug && isSystem,
    staleTime: 5 * 60_000,
  });
  return isSystem ? sysQuery : metaQuery;
}

/** Full schema snapshot for one entity. */
export function useEntity(entitySlug: string) {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  return useQuery({
    queryKey: ["meta", ws, "entity", entitySlug],
    queryFn: () => metadataApi.entity(entitySlug),
    enabled: isReady && !!ws && !!entitySlug,
    staleTime: 5 * 60_000,
  });
}
