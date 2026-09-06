/**
 * Feature-flag management client (Phase F2.9) — flag + override CRUD over `/api/v1/feature-flags/`
 * (backend Phase 1.29). Management is owner/admin. The resolved `/active/` flags are read by the
 * tenant context (see `lib/tenant`); this module is the admin surface.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type FlagScope = "workspace" | "role" | "user" | "global";
export type OverrideTarget = "workspace" | "role" | "user";

export interface FeatureFlag {
  id: string;
  key: string;
  name: string;
  description: string;
  enabled: boolean;
  rollout_percent: number;
  scope: FlagScope;
  config: Record<string, unknown>;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}
export interface FeatureFlagWrite {
  key: string;
  name?: string;
  description?: string;
  enabled?: boolean;
  rollout_percent?: number;
  scope?: FlagScope;
  is_active?: boolean;
}

export interface FeatureFlagOverride {
  id: string;
  flag: string;
  target_type: OverrideTarget;
  target_id: string | null;
  enabled: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}
export interface OverrideWrite {
  target_type: OverrideTarget;
  target_id?: string | null;
  enabled: boolean;
}

export const FLAG_SCOPES: { value: FlagScope; label: string }[] = [
  { value: "workspace", label: "Workspace" },
  { value: "role", label: "Role" },
  { value: "user", label: "User" },
  { value: "global", label: "Global" },
];
export const OVERRIDE_TARGETS: { value: OverrideTarget; label: string }[] = [
  { value: "workspace", label: "Whole workspace" },
  { value: "role", label: "Role" },
  { value: "user", label: "User" },
];

const F = "/api/v1/feature-flags";

export const featureFlagsApi = {
  list: () => apiGet<FeatureFlag[]>(`${F}/`),
  create: (data: FeatureFlagWrite) => apiSend<FeatureFlag>(`${F}/`, "POST", data),
  update: (id: string, data: Partial<FeatureFlagWrite>) => apiSend<FeatureFlag>(`${F}/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<null>(`${F}/${id}/`, "DELETE"),

  listOverrides: (flagId: string) => apiGet<FeatureFlagOverride[]>(`${F}/${flagId}/overrides/`),
  createOverride: (flagId: string, data: OverrideWrite) => apiSend<FeatureFlagOverride>(`${F}/${flagId}/overrides/`, "POST", data),
  removeOverride: (flagId: string, overrideId: string) => apiSend<null>(`${F}/${flagId}/overrides/${overrideId}/`, "DELETE"),
};
