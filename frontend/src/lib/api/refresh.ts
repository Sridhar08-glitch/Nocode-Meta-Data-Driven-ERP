/**
 * Single-flight refresh-token rotation (Phase F1.2).
 *
 * Concurrent 401s share ONE in-flight refresh — never a thundering herd of /refresh/
 * calls. On success both tokens rotate (backend invalidates the old refresh jti); on any
 * failure (incl. reuse-detection 401) we trigger a clean auth failure (logout).
 */
import { getRefreshToken, setTokens, triggerAuthFailure } from "@/lib/auth/token-store";

import { API_BASE_URL } from "./config";

let inFlight: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) {
    triggerAuthFailure();
    return false;
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });
  } catch {
    return false; // network error — keep tokens, let the caller surface it
  }
  if (!res.ok) {
    // 401 here = expired or reuse-detected family → log out cleanly.
    triggerAuthFailure();
    return false;
  }
  const data = (await res.json()) as { access: string; refresh: string };
  setTokens({ access: data.access, refresh: data.refresh });
  return true;
}

export function refreshAccessToken(): Promise<boolean> {
  inFlight ??= doRefresh().finally(() => {
    inFlight = null;
  });
  return inFlight;
}
