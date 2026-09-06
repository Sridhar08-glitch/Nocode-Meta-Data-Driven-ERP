/**
 * Portal Builder (custom admin) client (Phase F3.7) — config + portal users + entity grants over
 * `/api/v1/portal-admin/` (member owner/admin auth; outside the exempt `/portal/` realm). Portal user
 * passwords are write-only (hashed server-side, never returned). This is the ADMIN side; the portal
 * runtime (separate realm) lives in `lib/portal`.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface PortalConfig {
  id?: string;
  is_enabled: boolean;
  name: string;
  custom_domain: string;
  logo_url: string;
  primary_color: string;
  exposed_entity_ids: string[];
  default_role_id: string | null;
  allow_self_signup: boolean;
  signup_domain_whitelist: string[];
  welcome_message: string;
}
export interface PortalConfigWrite {
  is_enabled?: boolean;
  name?: string;
  logo_url?: string;
  primary_color?: string;
  exposed_entity_ids?: string[];
  allow_self_signup?: boolean;
  welcome_message?: string;
}

export interface PortalUser {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_verified: boolean;
  linked_entity_id: string | null;
  linked_record_id: string | null;
  role_id: string | null;
  portal_type: string;
  last_login_at: string | null;
}
export interface PortalUserWrite {
  email: string;
  full_name: string;
  password?: string;
  portal_type?: string;
  linked_entity_id?: string | null;
  linked_record_id?: string | null;
  is_active?: boolean;
}

export interface PortalGrant {
  id: string;
  entity_slug: string;
  portal_type: string;
  link_field: string;
  can_read: boolean;
  can_create: boolean;
  can_update: boolean;
}
export interface PortalGrantWrite {
  entity_slug: string;
  portal_type?: string;
  link_field: string;
  can_read?: boolean;
  can_create?: boolean;
  can_update?: boolean;
}

const P = "/api/v1/portal-admin";

export const portalAdminApi = {
  getConfig: () => apiGet<PortalConfig>(`${P}/config/`),
  updateConfig: (data: PortalConfigWrite) => apiSend<PortalConfig>(`${P}/config/`, "PATCH", data),

  listUsers: () => apiGet<{ results: PortalUser[]; count: number }>(`${P}/users/`),
  createUser: (data: PortalUserWrite) => apiSend<PortalUser>(`${P}/users/`, "POST", data),
  updateUser: (id: string, data: Partial<PortalUserWrite>) => apiSend<PortalUser>(`${P}/users/${id}/`, "PATCH", data),
  deleteUser: (id: string) => apiSend<null>(`${P}/users/${id}/`, "DELETE"),

  listGrants: () => apiGet<{ results: PortalGrant[]; count: number }>(`${P}/grants/`),
  createGrant: (data: PortalGrantWrite) => apiSend<PortalGrant>(`${P}/grants/`, "POST", data),
  deleteGrant: (id: string) => apiSend<null>(`${P}/grants/${id}/`, "DELETE"),
};
