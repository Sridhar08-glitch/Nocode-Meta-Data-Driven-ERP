/**
 * Permissions client (Phase F1.9) — RBAC + ABAC CRUD against `/api/v1/permissions/`.
 * Four owner/admin-only resource groups: roles, permissions (grants), field-permissions, and
 * data-masking rules. List endpoints return a bare JSON array (not paginated). `workspace_id`
 * is injected server-side and never sent in the body.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type ResourceType =
  | "workspace"
  | "module"
  | "entity"
  | "field"
  | "record"
  | "report"
  | "workflow"
  | "dashboard"
  | "document";

export type PermissionAction =
  | "create"
  | "read"
  | "update"
  | "delete"
  | "export"
  | "import"
  | "share"
  | "admin"
  | "*";

/** Operators supported by the ABAC condition engine. */
export type AbacOp =
  | "="
  | "!="
  | ">"
  | ">="
  | "<"
  | "<="
  | "in"
  | "not in"
  | "contains"
  | "is null"
  | "is not null";

export type MaskType = "full" | "first_n_chars" | "last_n_chars";

export interface AbacCondition {
  field: string;
  op: AbacOp;
  value?: unknown;
}

export interface Role {
  id: string;
  name: string;
  slug: string;
  description: string;
  is_system: boolean;
  is_active: boolean;
  parent_role: string | null;
  created_at?: string;
  updated_at?: string;
}
export interface RoleWrite {
  name: string;
  slug?: string;
  description?: string;
  is_active?: boolean;
  parent_role?: string | null;
}

export interface Permission {
  id: string;
  role: string;
  resource_type: ResourceType;
  resource_id: string | null;
  action: PermissionAction;
  is_deny: boolean;
  conditions: AbacCondition[];
  created_at?: string;
  updated_at?: string;
}
export interface PermissionWrite {
  role: string;
  resource_type: ResourceType;
  resource_id?: string | null;
  action: PermissionAction;
  is_deny?: boolean;
  conditions?: AbacCondition[];
}

export interface FieldPermission {
  id: string;
  field_id: string;
  role_id: string;
  can_read: boolean;
  can_write: boolean;
  created_at?: string;
  updated_at?: string;
}
export interface FieldPermissionWrite {
  field_id: string;
  role_id: string;
  can_read?: boolean;
  can_write?: boolean;
}

export interface MaskingRule {
  id: string;
  field_id: string;
  role_id: string;
  mask_type: MaskType;
  mask_pattern: string;
  created_at?: string;
  updated_at?: string;
}
export interface MaskingRuleWrite {
  field_id: string;
  role_id: string;
  mask_type: MaskType;
  mask_pattern?: string;
}

// ── picker options ───────────────────────────────────────────────────────────────────
export const RESOURCE_TYPE_OPTIONS: { value: ResourceType; label: string }[] = [
  { value: "workspace", label: "Workspace" },
  { value: "module", label: "Module" },
  { value: "entity", label: "Entity" },
  { value: "field", label: "Field" },
  { value: "record", label: "Record" },
  { value: "report", label: "Report" },
  { value: "workflow", label: "Workflow" },
  { value: "dashboard", label: "Dashboard" },
  { value: "document", label: "Document" },
];

export const ACTION_OPTIONS: { value: PermissionAction; label: string }[] = [
  { value: "*", label: "All actions" },
  { value: "create", label: "Create" },
  { value: "read", label: "Read" },
  { value: "update", label: "Update" },
  { value: "delete", label: "Delete" },
  { value: "export", label: "Export" },
  { value: "import", label: "Import" },
  { value: "share", label: "Share" },
  { value: "admin", label: "Admin" },
];

export const ABAC_OP_OPTIONS: { value: AbacOp; label: string }[] = [
  { value: "=", label: "equals" },
  { value: "!=", label: "not equals" },
  { value: ">", label: "greater than" },
  { value: ">=", label: "greater or equal" },
  { value: "<", label: "less than" },
  { value: "<=", label: "less or equal" },
  { value: "in", label: "in" },
  { value: "not in", label: "not in" },
  { value: "contains", label: "contains" },
  { value: "is null", label: "is empty" },
  { value: "is not null", label: "is not empty" },
];

export const MASK_TYPE_OPTIONS: { value: MaskType; label: string }[] = [
  { value: "full", label: "Full (***)" },
  { value: "first_n_chars", label: "Show first N chars" },
  { value: "last_n_chars", label: "Show last N chars" },
];

/** ABAC value tokens resolved server-side to the current user. */
export const ABAC_USER_TOKENS: { value: string; label: string }[] = [
  { value: "$user.id", label: "Current user id" },
  { value: "$me", label: "Current user (alias)" },
  { value: "$user.member_id", label: "Current membership id" },
];

function roleQuery(roleId?: string): string {
  return roleId ? `?role=${encodeURIComponent(roleId)}` : "";
}

export const permissionsApi = {
  // roles
  listRoles: () => apiGet<Role[]>("/api/v1/permissions/roles/"),
  createRole: (data: RoleWrite) => apiSend<Role>("/api/v1/permissions/roles/", "POST", data),
  updateRole: (id: string, data: Partial<RoleWrite>) =>
    apiSend<Role>(`/api/v1/permissions/roles/${id}/`, "PATCH", data),
  deleteRole: (id: string) => apiSend<null>(`/api/v1/permissions/roles/${id}/`, "DELETE"),

  // permission grants
  listPermissions: (roleId?: string) =>
    apiGet<Permission[]>(`/api/v1/permissions/permissions/${roleQuery(roleId)}`),
  createPermission: (data: PermissionWrite) =>
    apiSend<Permission>("/api/v1/permissions/permissions/", "POST", data),
  updatePermission: (id: string, data: Partial<PermissionWrite>) =>
    apiSend<Permission>(`/api/v1/permissions/permissions/${id}/`, "PATCH", data),
  deletePermission: (id: string) =>
    apiSend<null>(`/api/v1/permissions/permissions/${id}/`, "DELETE"),

  // field permissions
  listFieldPermissions: (roleId?: string) =>
    apiGet<FieldPermission[]>(`/api/v1/permissions/field-permissions/${roleQuery(roleId)}`),
  createFieldPermission: (data: FieldPermissionWrite) =>
    apiSend<FieldPermission>("/api/v1/permissions/field-permissions/", "POST", data),
  updateFieldPermission: (id: string, data: Partial<FieldPermissionWrite>) =>
    apiSend<FieldPermission>(`/api/v1/permissions/field-permissions/${id}/`, "PATCH", data),
  deleteFieldPermission: (id: string) =>
    apiSend<null>(`/api/v1/permissions/field-permissions/${id}/`, "DELETE"),

  // masking rules
  listMaskingRules: (roleId?: string) =>
    apiGet<MaskingRule[]>(`/api/v1/permissions/masking-rules/${roleQuery(roleId)}`),
  createMaskingRule: (data: MaskingRuleWrite) =>
    apiSend<MaskingRule>("/api/v1/permissions/masking-rules/", "POST", data),
  updateMaskingRule: (id: string, data: Partial<MaskingRuleWrite>) =>
    apiSend<MaskingRule>(`/api/v1/permissions/masking-rules/${id}/`, "PATCH", data),
  deleteMaskingRule: (id: string) =>
    apiSend<null>(`/api/v1/permissions/masking-rules/${id}/`, "DELETE"),
};
