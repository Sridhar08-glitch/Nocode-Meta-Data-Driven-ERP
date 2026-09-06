/**
 * Portal runtime client (Phase F3.7) — the external portal auth realm + scoped data over
 * `/api/v1/portal/` (backend Phase 1.5 auth + 1.34 data). Uses the isolated portal token store, NOT
 * the member `authFetch`. Row isolation is SERVER-enforced (PortalDataService AND-injects the
 * link_field = the user's linked record); the client only ever calls the scoped endpoints.
 */
import { API_BASE_URL } from "@/lib/api/config";
import { ApiError, toApiError } from "@/lib/api/errors";

import {
  clearPortalTokens,
  getPortalAccess,
  getPortalRefresh,
  setPortalTokens,
} from "./token-store";

export interface PortalSessionUser {
  id: string;
  email: string;
  workspace_id: string;
  full_name?: string;
  portal_type?: string;
}
export interface PortalRecord {
  id: string;
  [key: string]: unknown;
}

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) throw toApiError(res, body);
  return body as T;
}

/** Raw POST (no auth header) — for login/refresh. */
async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<T>(res);
}

/** Authenticated fetch with the PORTAL access token; refresh-once on 401. */
async function portalFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const withAuth = (token: string | null): RequestInit => ({
    ...init,
    headers: { ...(init.headers ?? {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });

  let res = await fetch(`${API_BASE_URL}${path}`, withAuth(getPortalAccess()));
  if (res.status === 401 && getPortalRefresh()) {
    try {
      const r = await post<{ access: string; refresh: string }>("/api/v1/portal/auth/refresh/", { refresh: getPortalRefresh() });
      setPortalTokens({ access: r.access, refresh: r.refresh });
      res = await fetch(`${API_BASE_URL}${path}`, withAuth(getPortalAccess()));
    } catch {
      clearPortalTokens();
    }
  }
  return res;
}

async function authedGet<T>(path: string): Promise<T> {
  return parse<T>(await portalFetch(path));
}
async function authedSend<T>(path: string, method: string, body?: unknown): Promise<T> {
  return parse<T>(await portalFetch(path, { method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }));
}

export const portalApi = {
  async login(workspaceSlug: string, email: string, password: string): Promise<PortalSessionUser> {
    const r = await post<{ access: string; refresh: string; portal_user: PortalSessionUser }>(
      "/api/v1/portal/auth/login/",
      { workspace_slug: workspaceSlug, email, password },
    );
    setPortalTokens({ access: r.access, refresh: r.refresh, slug: workspaceSlug });
    return r.portal_user;
  },
  async logout(): Promise<void> {
    const refresh = getPortalRefresh();
    if (refresh) {
      try {
        await post("/api/v1/portal/auth/logout/", { refresh });
      } catch {
        /* best-effort */
      }
    }
    clearPortalTokens();
  },
  me: () => authedGet<PortalSessionUser>("/api/v1/portal/auth/me/"),
  listRecords: (entitySlug: string) => authedGet<{ results: PortalRecord[]; count: number }>(`/api/v1/portal/data/${entitySlug}/`),
  getRecord: (entitySlug: string, id: string) => authedGet<PortalRecord>(`/api/v1/portal/data/${entitySlug}/${id}/`),
  createRecord: (entitySlug: string, data: Record<string, unknown>) => authedSend<PortalRecord>(`/api/v1/portal/data/${entitySlug}/`, "POST", data),
};

export { ApiError };
