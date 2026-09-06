import { create } from "zustand";

/**
 * Tenant context (Phase F0 minimal).
 *
 * The backend resolves the active workspace from the **`X-Workspace-Slug`** header
 * (apps/tenancy/middleware.py) — NOT a numeric tenant id. F1.4 expands this with plan,
 * flags, rateLimits, schemaVersion; F0 holds the slug the API client injects.
 */
interface TenantState {
  workspaceSlug: string | null;
  setWorkspaceSlug: (slug: string | null) => void;
}

export const useTenantStore = create<TenantState>((set) => ({
  workspaceSlug: null,
  setWorkspaceSlug: (slug) => set({ workspaceSlug: slug }),
}));

/** Non-React accessor for the API client (which runs outside component scope). */
export function getWorkspaceSlug(): string | null {
  return useTenantStore.getState().workspaceSlug;
}
