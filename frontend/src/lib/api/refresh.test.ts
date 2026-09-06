import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  registerAuthFailureHandler,
  setTokens,
} from "@/lib/auth/token-store";

import { refreshAccessToken } from "./refresh";

describe("refreshAccessToken (single-flight rotation)", () => {
  beforeEach(() => {
    clearTokens();
    registerAuthFailureHandler(null);
    vi.restoreAllMocks();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("returns false and triggers logout when there is no refresh token", async () => {
    const onFail = vi.fn();
    registerAuthFailureHandler(onFail);
    const ok = await refreshAccessToken();
    expect(ok).toBe(false);
    expect(onFail).toHaveBeenCalledOnce();
  });

  it("rotates both tokens on success", async () => {
    setTokens({ access: "a1", refresh: "r1" });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ access: "a2", refresh: "r2" }), { status: 200 })),
    );
    const ok = await refreshAccessToken();
    expect(ok).toBe(true);
    expect(getAccessToken()).toBe("a2");
    expect(getRefreshToken()).toBe("r2");
  });

  it("triggers clean logout on a reuse-detection 401", async () => {
    setTokens({ access: "a1", refresh: "stale" });
    const onFail = vi.fn();
    registerAuthFailureHandler(onFail);
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 401 })));
    const ok = await refreshAccessToken();
    expect(ok).toBe(false);
    expect(onFail).toHaveBeenCalledOnce();
    expect(getRefreshToken()).toBeNull();
  });

  it("returns false (without logout) on a network error", async () => {
    setTokens({ access: "a1", refresh: "r1" });
    const onFail = vi.fn();
    registerAuthFailureHandler(onFail);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("network down");
      }),
    );
    const ok = await refreshAccessToken();
    expect(ok).toBe(false);
    expect(onFail).not.toHaveBeenCalled();
    expect(getRefreshToken()).toBe("r1"); // tokens preserved
  });

  it("coalesces concurrent callers into a single network refresh", async () => {
    setTokens({ access: "a1", refresh: "r1" });
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ access: "a2", refresh: "r2" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const [first, second] = await Promise.all([refreshAccessToken(), refreshAccessToken()]);
    expect(first).toBe(true);
    expect(second).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
