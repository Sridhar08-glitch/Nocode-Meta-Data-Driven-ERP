/**
 * Portal token store (Phase F3.7) — a SEPARATE realm from the workspace member session.
 *
 * Deliberately isolated from `lib/auth/token-store` (members): different localStorage key, its own
 * in-memory access token. A portal user is NOT a workspace member; nothing here ever reads or writes
 * the member tokens, so the two realms can't cross-contaminate. Access token in memory; rotating
 * refresh persisted so a reload keeps the portal session.
 */
const LS_REFRESH = "nexus.portal.refresh";
const LS_SLUG = "nexus.portal.ws";

let accessToken: string | null = null;
let refreshToken: string | null = null;

if (typeof window !== "undefined") {
  try {
    refreshToken = window.localStorage.getItem(LS_REFRESH);
  } catch {
    refreshToken = null;
  }
}

export function getPortalAccess(): string | null {
  return accessToken;
}
export function getPortalRefresh(): string | null {
  return refreshToken;
}
export function getPortalWorkspace(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(LS_SLUG);
  } catch {
    return null;
  }
}

export function setPortalTokens({ access, refresh, slug }: { access: string; refresh: string; slug?: string }): void {
  accessToken = access;
  refreshToken = refresh;
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LS_REFRESH, refresh);
    if (slug) window.localStorage.setItem(LS_SLUG, slug);
  } catch {
    /* memory-only this run */
  }
}

export function setPortalAccess(token: string | null): void {
  accessToken = token;
}

export function clearPortalTokens(): void {
  accessToken = null;
  refreshToken = null;
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(LS_REFRESH);
    window.localStorage.removeItem(LS_SLUG);
  } catch {
    /* ignore */
  }
}
