/**
 * Auth interceptor fetch (Phase F1.2) — the load-bearing client wrapper.
 *
 * Responsibilities (wrong-once-wrong-everywhere → 100% covered):
 *   1. inject `Authorization`, `X-Workspace-Slug`, `X-Request-ID` on every request;
 *   2. on a 401, run a single-flight refresh and retry the request **exactly once**
 *      with the new access token;
 *   3. if refresh fails → clean logout (the refresh layer triggers it) and surface the 401.
 *
 * All collaborators are injected so this is a pure, testable unit (no globals).
 */
export interface AuthFetchDeps {
  baseFetch: typeof fetch;
  getAccessToken: () => string | null;
  getWorkspaceSlug: () => string | null;
  refresh: () => Promise<boolean>;
  newRequestId?: () => string;
}

function defaultRequestId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `req-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}

export function createAuthFetch(deps: AuthFetchDeps): typeof fetch {
  const requestId = deps.newRequestId ?? defaultRequestId;

  const withAuthHeaders = (input: RequestInfo | URL, init: RequestInit | undefined): Request => {
    const req = new Request(input, init);
    const token = deps.getAccessToken();
    if (token) req.headers.set("Authorization", `Bearer ${token}`);
    const slug = deps.getWorkspaceSlug();
    if (slug) req.headers.set("X-Workspace-Slug", slug);
    req.headers.set("X-Request-ID", requestId());
    return req;
  };

  return async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    // Clone the body source so we can rebuild the request for a retry.
    const bodyInit = init?.body ?? null;
    const first = await deps.baseFetch(withAuthHeaders(input, init));
    if (first.status !== 401) return first;

    const refreshed = await deps.refresh();
    if (!refreshed) return first; // refresh layer already triggered logout

    // Retry exactly once with the rotated access token.
    const retryInit: RequestInit = { ...init, body: bodyInit ?? undefined };
    return deps.baseFetch(withAuthHeaders(input, retryInit));
  };
}
