/**
 * Studio client (Phase F2.8) — Applications, Home Layouts, Navigation over `/api/v1/applications/`,
 * `/api/v1/home-layouts/`, `/api/v1/navigation/` (backend Phase 1.32). Reads + switcher/resolve are
 * open to any member; create/update/delete/publish are owner/admin. Draft→Publish = `is_published`.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface Paged<T> {
  results: T[];
  count: number;
}

// ── Applications ──────────────────────────────────────────────────────────────────
export interface Application {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  color: string;
  included_entity_ids: string[];
  navigation_id: string | null;
  home_layout_id: string | null;
  role_ids: string[];
  theme_overrides: Record<string, string>;
  order: number;
  is_published: boolean;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}
export interface ApplicationWrite {
  name: string;
  slug: string;
  description?: string;
  icon?: string;
  color?: string;
  included_entity_ids?: string[];
  navigation_id?: string | null;
  home_layout_id?: string | null;
  role_ids?: string[];
  theme_overrides?: Record<string, string>;
  order?: number;
  is_active?: boolean;
}

// ── Home Layouts ──────────────────────────────────────────────────────────────────
export type LayoutScope = "workspace" | "app" | "role" | "personal";
export interface HomeWidget {
  type: string;
  title?: string;
  width?: number;
  config?: Record<string, unknown>;
}
export interface HomeLayout {
  id: string;
  name: string;
  scope: LayoutScope;
  target_id: string | null;
  widgets: HomeWidget[];
  is_published: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}
export interface HomeLayoutWrite {
  name: string;
  scope: LayoutScope;
  target_id?: string | null;
  widgets?: HomeWidget[];
}

// ── Navigation ──────────────────────────────────────────────────────────────────
export type NavScope = "workspace" | "app" | "role";
export type NavItemType = "entity" | "internal" | "external";
export interface NavItem {
  label: string;
  type: NavItemType;
  target: string;
  icon?: string;
  roles?: string[];
}
export interface NavGroup {
  label: string;
  roles?: string[];
  items: NavItem[];
}
export interface Navigation {
  id: string;
  name: string;
  scope: NavScope;
  target_id: string | null;
  tree: NavGroup[];
  is_published: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}
export interface NavigationWrite {
  name: string;
  scope: NavScope;
  target_id?: string | null;
  tree?: NavGroup[];
}
/** Shape returned by `/navigation/resolve/` (role-filtered, app→workspace fallback). */
export interface ResolvedNavigation {
  id: string;
  name: string;
  scope: NavScope;
  groups: NavGroup[];
}

export const LAYOUT_SCOPES: { value: LayoutScope; label: string }[] = [
  { value: "workspace", label: "Workspace (default)" },
  { value: "app", label: "Application" },
  { value: "role", label: "Role" },
  { value: "personal", label: "Personal" },
];
export const NAV_SCOPES: { value: NavScope; label: string }[] = [
  { value: "workspace", label: "Workspace (default)" },
  { value: "app", label: "Application" },
  { value: "role", label: "Role" },
];
export const NAV_ITEM_TYPES: { value: NavItemType; label: string }[] = [
  { value: "entity", label: "Entity" },
  { value: "internal", label: "Internal link" },
  { value: "external", label: "External link" },
];
export const HOME_WIDGET_TYPES: { value: string; label: string }[] = [
  { value: "report", label: "Report" },
  { value: "metric", label: "Metric" },
  { value: "list", label: "Record list" },
  { value: "text", label: "Text / note" },
];

const A = "/api/v1/applications";
const H = "/api/v1/home-layouts";
const N = "/api/v1/navigation";

export const studioApi = {
  // applications
  listApps: () => apiGet<Paged<Application>>(`${A}/`),
  switcher: () => apiGet<Paged<Application>>(`${A}/switcher/`),
  getApp: (id: string) => apiGet<Application>(`${A}/${id}/`),
  createApp: (data: ApplicationWrite) => apiSend<Application>(`${A}/`, "POST", data),
  updateApp: (id: string, data: Partial<ApplicationWrite>) => apiSend<Application>(`${A}/${id}/`, "PATCH", data),
  deleteApp: (id: string) => apiSend<null>(`${A}/${id}/`, "DELETE"),
  publishApp: (id: string) => apiSend<Application>(`${A}/${id}/publish/`, "POST"),

  // home layouts
  listHome: () => apiGet<Paged<HomeLayout>>(`${H}/`),
  resolveHome: (appId?: string) => apiGet<HomeLayout | Record<string, never>>(`${H}/resolve/${appId ? `?app=${appId}` : ""}`),
  createHome: (data: HomeLayoutWrite) => apiSend<HomeLayout>(`${H}/`, "POST", data),
  updateHome: (id: string, data: Partial<HomeLayoutWrite>) => apiSend<HomeLayout>(`${H}/${id}/`, "PATCH", data),
  deleteHome: (id: string) => apiSend<null>(`${H}/${id}/`, "DELETE"),
  publishHome: (id: string) => apiSend<HomeLayout>(`${H}/${id}/publish/`, "POST"),

  // navigation
  listNav: () => apiGet<Paged<Navigation>>(`${N}/`),
  resolveNav: (appId?: string) => apiGet<ResolvedNavigation | Record<string, never>>(`${N}/resolve/${appId ? `?app=${appId}` : ""}`),
  createNav: (data: NavigationWrite) => apiSend<Navigation>(`${N}/`, "POST", data),
  updateNav: (id: string, data: Partial<NavigationWrite>) => apiSend<Navigation>(`${N}/${id}/`, "PATCH", data),
  deleteNav: (id: string) => apiSend<null>(`${N}/${id}/`, "DELETE"),
  publishNav: (id: string) => apiSend<Navigation>(`${N}/${id}/publish/`, "POST"),
};
