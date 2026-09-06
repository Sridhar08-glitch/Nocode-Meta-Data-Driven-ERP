import { apiGet } from "@/lib/api/request";
import type { WorkspaceBranding } from "@/lib/branding/apply";
import type { FeatureFlags, Workspace } from "@/lib/tenant/types";

import type { EntityMeta, FormSchema, ModuleMeta } from "./types";

export const metadataApi = {
  workspaces: () => apiGet<Workspace[]>("/api/v1/workspaces/"),
  modules: () => apiGet<ModuleMeta[]>("/api/v1/metadata/modules/"),
  entities: () => apiGet<EntityMeta[]>("/api/v1/metadata/entities/"),
  /** Full entity schema snapshot (entity + fields). */
  entity: (slug: string) => apiGet<EntityMeta>(`/api/v1/metadata/entities/${slug}/`),
  /** The canonical, permission-resolved FormSchema (§1.26). */
  formSchema: (slug: string) =>
    apiGet<FormSchema>(`/api/v1/metadata/entities/${slug}/form-schema/`),
  relationships: () => apiGet<unknown[]>("/api/v1/relationships/"),
  branding: () => apiGet<WorkspaceBranding>("/api/v1/branding/"),
  activeFlags: () => apiGet<{ flags: FeatureFlags }>("/api/v1/feature-flags/active/"),
};
