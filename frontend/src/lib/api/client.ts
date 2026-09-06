/**
 * The ONE typed API client (Phase F0 → hardened in F1.2).
 *
 * `openapi-fetch` over generated `paths`, using the auth-interceptor fetch
 * (`createAuthFetch`) for header injection + single-flight refresh + one-retry-on-401.
 * Grounded in the real backend: tenant is keyed by the **`X-Workspace-Slug`** header
 * (not `X-Tenant-ID`); `Accept-Language` is deferred until it's added to backend CORS.
 */
import createClient from "openapi-fetch";

import { getAccessToken } from "@/lib/auth/token-store";
import { getWorkspaceSlug } from "@/lib/tenant/store";

import { createAuthFetch } from "./auth-fetch";
import { API_BASE_URL } from "./config";
import { refreshAccessToken } from "./refresh";
import type { paths } from "./schema";

export { API_BASE_URL };

export const authFetch = createAuthFetch({
  baseFetch: (input, init) => fetch(input, init),
  getAccessToken,
  getWorkspaceSlug,
  refresh: refreshAccessToken,
});

export const api = createClient<paths>({ baseUrl: API_BASE_URL, fetch: authFetch });
