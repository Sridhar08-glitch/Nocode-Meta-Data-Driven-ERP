/**
 * Query-key factory (Phase F1.2).
 *
 * Every key is namespaced by the active **tenant (workspace slug)** and, where the data
 * depends on schema, the **schemaVersion** — so switching workspace or publishing a
 * config change cleanly invalidates the right caches (no cross-tenant bleed).
 */
export type TenantScope = { tenant: string | null; schemaVersion?: number | string };

export const queryKeys = {
  /** Tenant context payload (workspaces, plan, flags, schemaVersion) — F1.4. */
  tenantContext: (tenant: string | null) => ["tenant", tenant, "context"] as const,

  metadata: {
    entities: (s: TenantScope) => ["meta", s.tenant, s.schemaVersion ?? "v", "entities"] as const,
    entity: (s: TenantScope, slug: string) =>
      ["meta", s.tenant, s.schemaVersion ?? "v", "entity", slug] as const,
    formSchema: (s: TenantScope, slug: string) =>
      ["meta", s.tenant, s.schemaVersion ?? "v", "form-schema", slug] as const,
  },

  records: {
    list: (s: TenantScope, entity: string, params?: unknown) =>
      ["data", s.tenant, s.schemaVersion ?? "v", entity, "list", params ?? null] as const,
    detail: (s: TenantScope, entity: string, id: string) =>
      ["data", s.tenant, s.schemaVersion ?? "v", entity, "detail", id] as const,
  },

  notifications: {
    list: (tenant: string | null) => ["notifications", tenant, "list"] as const,
    unreadCount: (tenant: string | null) => ["notifications", tenant, "unread-count"] as const,
  },
} as const;
