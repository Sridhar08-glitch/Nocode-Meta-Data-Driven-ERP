import { beforeEach, describe, expect, it, vi } from "vitest";

import { createAuthFetch, type AuthFetchDeps } from "./auth-fetch";

function makeDeps(overrides: Partial<AuthFetchDeps> = {}): {
  deps: AuthFetchDeps;
  baseFetch: ReturnType<typeof vi.fn>;
  refresh: ReturnType<typeof vi.fn>;
} {
  const baseFetch = vi.fn();
  const refresh = vi.fn(async () => true);
  const deps: AuthFetchDeps = {
    baseFetch: baseFetch as unknown as typeof fetch,
    getAccessToken: () => "access-1",
    getWorkspaceSlug: () => "acme",
    refresh: refresh as unknown as () => Promise<boolean>,
    newRequestId: () => "fixed-id",
    ...overrides,
  };
  return { deps, baseFetch, refresh };
}

const ok = () => new Response("{}", { status: 200 });
const unauthorized = () => new Response("{}", { status: 401 });

describe("createAuthFetch", () => {
  beforeEach(() => vi.clearAllMocks());

  it("injects Authorization, X-Workspace-Slug and X-Request-ID", async () => {
    const { deps, baseFetch } = makeDeps();
    baseFetch.mockResolvedValueOnce(ok());
    const authFetch = createAuthFetch(deps);
    await authFetch("http://api/x");
    const req = baseFetch.mock.calls[0][0] as Request;
    expect(req.headers.get("Authorization")).toBe("Bearer access-1");
    expect(req.headers.get("X-Workspace-Slug")).toBe("acme");
    expect(req.headers.get("X-Request-ID")).toBe("fixed-id");
  });

  it("omits Authorization/slug when none are set", async () => {
    const { deps, baseFetch } = makeDeps({
      getAccessToken: () => null,
      getWorkspaceSlug: () => null,
    });
    baseFetch.mockResolvedValueOnce(ok());
    await createAuthFetch(deps)("http://api/x");
    const req = baseFetch.mock.calls[0][0] as Request;
    expect(req.headers.get("Authorization")).toBeNull();
    expect(req.headers.get("X-Workspace-Slug")).toBeNull();
    expect(req.headers.get("X-Request-ID")).toBe("fixed-id");
  });

  it("passes through non-401 responses without refreshing", async () => {
    const { deps, baseFetch, refresh } = makeDeps();
    baseFetch.mockResolvedValueOnce(ok());
    const res = await createAuthFetch(deps)("http://api/x");
    expect(res.status).toBe(200);
    expect(refresh).not.toHaveBeenCalled();
    expect(baseFetch).toHaveBeenCalledTimes(1);
  });

  it("on 401 → refresh succeeds → retries once and returns the retry response", async () => {
    const { deps, baseFetch, refresh } = makeDeps();
    baseFetch.mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(ok());
    const res = await createAuthFetch(deps)("http://api/x");
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(baseFetch).toHaveBeenCalledTimes(2);
    expect(res.status).toBe(200);
  });

  it("uses the rotated token on the retry", async () => {
    let token = "old";
    const { deps, baseFetch } = makeDeps({
      getAccessToken: () => token,
      refresh: (async () => {
        token = "new";
        return true;
      }) as unknown as () => Promise<boolean>,
    });
    baseFetch.mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(ok());
    await createAuthFetch(deps)("http://api/x");
    const retryReq = baseFetch.mock.calls[1][0] as Request;
    expect(retryReq.headers.get("Authorization")).toBe("Bearer new");
  });

  it("on 401 → refresh fails → returns the original 401 without retrying", async () => {
    const { deps, baseFetch, refresh } = makeDeps({
      refresh: vi.fn(async () => false) as unknown as () => Promise<boolean>,
    });
    baseFetch.mockResolvedValueOnce(unauthorized());
    const res = await createAuthFetch(deps)("http://api/x");
    expect(res.status).toBe(401);
    expect(baseFetch).toHaveBeenCalledTimes(1);
    void refresh;
  });

  it("retries at most once (a still-401 retry is returned, refresh called once)", async () => {
    const { deps, baseFetch, refresh } = makeDeps();
    baseFetch.mockResolvedValue(unauthorized());
    const res = await createAuthFetch(deps)("http://api/x");
    expect(res.status).toBe(401);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(baseFetch).toHaveBeenCalledTimes(2);
  });

  it("preserves method + body on the retried request", async () => {
    const { deps, baseFetch } = makeDeps();
    baseFetch.mockResolvedValueOnce(unauthorized()).mockResolvedValueOnce(ok());
    await createAuthFetch(deps)("http://api/x", {
      method: "POST",
      body: JSON.stringify({ a: 1 }),
    });
    const retry = baseFetch.mock.calls[1][0] as Request;
    expect(retry.method).toBe("POST");
    await expect(retry.text()).resolves.toContain('"a":1');
  });

  it("falls back to a generated request id when none is provided", async () => {
    const { deps, baseFetch } = makeDeps({ newRequestId: undefined });
    baseFetch.mockResolvedValueOnce(ok());
    await createAuthFetch(deps)("http://api/x");
    const req = baseFetch.mock.calls[0][0] as Request;
    expect(req.headers.get("X-Request-ID")).toBeTruthy();
  });

  it("uses the non-crypto request-id fallback when crypto.randomUUID throws", async () => {
    const spy = vi.spyOn(globalThis.crypto, "randomUUID").mockImplementation(() => {
      throw new Error("unavailable");
    });
    const { deps, baseFetch } = makeDeps({ newRequestId: undefined });
    baseFetch.mockResolvedValueOnce(ok());
    await createAuthFetch(deps)("http://api/x");
    const req = baseFetch.mock.calls[0][0] as Request;
    expect(req.headers.get("X-Request-ID")).toMatch(/^req-/);
    spy.mockRestore();
  });
});
