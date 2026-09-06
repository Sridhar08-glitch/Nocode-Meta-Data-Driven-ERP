/**
 * Token store (Phase F1.2).
 *
 * Access token lives in memory only; the rotating refresh token is persisted to
 * localStorage so a reload can re-establish a session. The backend's refresh-token
 * **rotation + reuse detection** (apps/accounts/tokens.py) is the compensating control:
 * a stolen/stale refresh triggers family revocation → our interceptor logs out cleanly.
 */
const LS_REFRESH_KEY = "nexus.refresh";

let accessToken: string | null = null;
let refreshToken: string | null = null;
let authFailureHandler: (() => void) | null = null;

// Hydrate the refresh token from storage on the client.
if (typeof window !== "undefined") {
  try {
    refreshToken = window.localStorage.getItem(LS_REFRESH_KEY);
  } catch {
    refreshToken = null;
  }
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getRefreshToken(): string | null {
  return refreshToken;
}

export function setTokens({ access, refresh }: { access: string; refresh: string }): void {
  accessToken = access;
  refreshToken = refresh;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(LS_REFRESH_KEY, refresh);
    } catch {
      /* storage unavailable — session is memory-only this run */
    }
  }
}

export function clearTokens(): void {
  accessToken = null;
  refreshToken = null;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem(LS_REFRESH_KEY);
    } catch {
      /* ignore */
    }
  }
}

/** Register the "logout + redirect" behaviour the app wants on auth failure. */
export function registerAuthFailureHandler(fn: (() => void) | null): void {
  authFailureHandler = fn;
}

/** Clear tokens and run the registered handler (e.g. redirect to /login). */
export function triggerAuthFailure(): void {
  clearTokens();
  authFailureHandler?.();
}
