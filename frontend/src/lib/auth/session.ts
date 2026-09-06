/**
 * Client auth session (Phase F1.3).
 *
 * Holds the current user (Zustand), applies token responses, and owns logout. A
 * non-sensitive presence cookie (`nexus_auth`) lets `middleware.ts` gate protected routes
 * without exposing tokens (the access token stays in memory; real validation is the API
 * 401→refresh→logout path).
 */
import { create } from "zustand";

import { clearTokens, setTokens } from "@/lib/auth/token-store";

import type { AuthUser, TokenResponse } from "./api";
import { AUTH_COOKIE } from "./constants";
import { decodeJwtPayload } from "./jwt";

export { AUTH_COOKIE };

interface AuthState {
  user: AuthUser | null;
  setUser: (user: AuthUser | null) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
}));

function setAuthCookie(present: boolean) {
  if (typeof document === "undefined") return;
  document.cookie = present
    ? `${AUTH_COOKIE}=1; path=/; max-age=2592000; SameSite=Lax`
    : `${AUTH_COOKIE}=; path=/; max-age=0; SameSite=Lax`;
}

/** Persist tokens + user after a successful login/verify, and flip the presence cookie. */
export function applyTokenResponse(res: TokenResponse): void {
  setTokens({ access: res.access, refresh: res.refresh });
  setAuthCookie(true);
  useAuthStore.getState().setUser(res.user);
}

/** Apply tokens from the OAuth callback hash; derive a minimal user from the JWT claims
 *  (the full profile loads with the tenant context in F1.4). */
export function applyOAuthTokens(access: string, refresh: string): boolean {
  const claims = decodeJwtPayload(access);
  if (!claims?.user_id) return false;
  setTokens({ access, refresh });
  setAuthCookie(true);
  useAuthStore.getState().setUser({
    id: String(claims.user_id),
    email: typeof claims.email === "string" ? claims.email : "",
    full_name: "",
    mfa_enabled: false,
  });
  return true;
}

/** Clear everything and send the user to /login. */
export function logout(redirect = true): void {
  clearTokens();
  setAuthCookie(false);
  useAuthStore.getState().setUser(null);
  if (redirect && typeof window !== "undefined") {
    window.location.assign("/login");
  }
}
