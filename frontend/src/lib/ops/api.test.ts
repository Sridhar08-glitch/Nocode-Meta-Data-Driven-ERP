import { beforeEach, describe, expect, it, vi } from "vitest";

const authFetch = vi.fn();
vi.mock("@/lib/api/client", () => ({ authFetch: (...a: unknown[]) => authFetch(...a) }));
vi.mock("@/lib/api/config", () => ({ API_BASE_URL: "http://api.test" }));

import { fetchReadiness } from "./api";

function resp(status: number, body: unknown) {
  return { status, text: () => Promise.resolve(JSON.stringify(body)) } as unknown as Response;
}

beforeEach(() => authFetch.mockReset());

describe("fetchReadiness", () => {
  it("hits /readyz/ at the API root (not /api/v1/)", async () => {
    authFetch.mockResolvedValue(resp(200, { status: "ready", checks: {} }));
    await fetchReadiness();
    expect(authFetch).toHaveBeenCalledWith("http://api.test/readyz/");
  });

  it("parses the 503 not-ready body instead of throwing", async () => {
    authFetch.mockResolvedValue(
      resp(503, { status: "not_ready", checks: { broker: { ok: false, detail: "down", latency_ms: 0 } } }),
    );
    const data = await fetchReadiness();
    expect(data.status).toBe("not_ready");
    expect(data.checks.broker.ok).toBe(false);
  });

  it("throws on an unexpected status", async () => {
    authFetch.mockResolvedValue(resp(500, {}));
    await expect(fetchReadiness()).rejects.toThrow(/readiness probe failed/);
  });
});
