import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Isolated portal token store — spy on it to prove the realm separation.
const store = vi.hoisted(() => ({
  access: "PORTAL_ACCESS" as string | null,
  refresh: "PORTAL_REFRESH" as string | null,
  set: vi.fn(),
  setAccess: vi.fn(),
  clear: vi.fn(),
}));
vi.mock("./token-store", () => ({
  getPortalAccess: () => store.access,
  getPortalRefresh: () => store.refresh,
  setPortalTokens: store.set,
  setPortalAccess: store.setAccess,
  clearPortalTokens: store.clear,
}));
vi.mock("@/lib/api/config", () => ({ API_BASE_URL: "http://api.test" }));

import { portalApi } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status < 400, status, text: () => Promise.resolve(JSON.stringify(body)) } as unknown as Response;
}

const fetchMock = vi.fn();

beforeEach(() => {
  store.access = "PORTAL_ACCESS";
  store.refresh = "PORTAL_REFRESH";
  store.set.mockClear();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("portalApi (separate realm)", () => {
  it("logs in against the workspace and stores portal tokens", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ access: "A", refresh: "R", portal_user: { id: "p1", email: "c@a.com", workspace_id: "w1" } }));
    const user = await portalApi.login("acme", "c@a.com", "pw");
    expect(user.id).toBe("p1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/portal/auth/login/");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ workspace_slug: "acme", email: "c@a.com", password: "pw" });
    expect(store.set).toHaveBeenCalledWith({ access: "A", refresh: "R", slug: "acme" });
  });

  it("calls the SCOPED data endpoint with the PORTAL token (not member auth)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ results: [{ id: "r1" }], count: 1 }));
    const res = await portalApi.listRecords("ticket");
    expect(res.count).toBe(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/portal/data/ticket/");
    expect((init as RequestInit).headers).toMatchObject({ Authorization: "Bearer PORTAL_ACCESS" });
  });

  it("refreshes once on 401 then retries with the new token", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ access: "A2", refresh: "R2" }))
      .mockResolvedValueOnce(jsonResponse({ results: [], count: 0 }));
    await portalApi.me();
    expect(fetchMock.mock.calls[1][0]).toBe("http://api.test/api/v1/portal/auth/refresh/");
    expect(store.set).toHaveBeenCalledWith({ access: "A2", refresh: "R2" });
  });
});
