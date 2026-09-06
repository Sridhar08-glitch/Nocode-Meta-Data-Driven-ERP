"use client";

import { useQuery } from "@tanstack/react-query";

import type { EntityMeta } from "@/lib/metadata/types";
import { useTenant } from "@/lib/tenant/context";

import { descriptorToEntityMeta, type SystemEntityListItem } from "./adapt";
import { systemEntitiesApi } from "./api";

/** Raw list of registered system entities for the workspace (lightweight — no fields). */
export function useSystemEntityList() {
  const { workspace, isReady } = useTenant();
  const slug = workspace?.slug ?? null;
  return useQuery({
    queryKey: ["sysent", slug, "list"],
    queryFn: systemEntitiesApi.list,
    enabled: isReady && !!slug,
    staleTime: 5 * 60_000,
  });
}

/** System entities as lightweight `EntityMeta` (kind:"system") for the merged runtime list + nav.
 *  `settled` is true once the query resolves EITHER way — a system-entities error (e.g. an older
 *  backend without the endpoint) degrades to "no system entities" so metadata entities are never
 *  blocked (backward compatibility). */
export function useSystemEntitiesAsMeta(): {
  data: EntityMeta[];
  isSuccess: boolean;
  settled: boolean;
} {
  const q = useSystemEntityList();
  const data = (q.isError ? [] : (q.data ?? [])).map(listItemToMeta);
  return { data, isSuccess: q.isSuccess, settled: q.isSuccess || q.isError };
}

function listItemToMeta(e: SystemEntityListItem): EntityMeta {
  return {
    id: e.slug,
    slug: e.slug,
    name: e.name,
    plural_name: e.plural_name,
    description: "",
    icon: "",
    color: "",
    module: e.module || null,
    is_active: true,
    title_field_slug: "",
    current_schema_version: 0,
    fields: [],
    can_read: e.can_read,
    can_create: e.can_create,
    kind: "system",
  };
}

/** Full descriptor for one system entity (fetched only when the slug is a system entity). */
export function useSystemEntityDescriptor(slug: string, enabled: boolean) {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  return useQuery({
    queryKey: ["sysent", ws, "descriptor", slug],
    queryFn: () => systemEntitiesApi.descriptor(slug),
    enabled: isReady && !!ws && !!slug && enabled,
    staleTime: 5 * 60_000,
    select: descriptorToEntityMeta,
  });
}
