import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/config", () => ({ API_BASE_URL: "http://api.test" }));
import { publicFormsApi } from "./api";

const fetchMock = vi.fn();
function res(body: unknown, status = 200): Response {
  return { ok: status < 400, status, text: () => Promise.resolve(JSON.stringify(body)) } as unknown as Response;
}

beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => vi.unstubAllGlobals());

describe("publicFormsApi (unauthenticated)", () => {
  it("fetches the public schema with no auth header", async () => {
    fetchMock.mockResolvedValueOnce(res({ form_id: "f1", name: "X", entity_slug: "lead", honeypot_field: "_hp", settings: {}, schema: {} }));
    const r = await publicFormsApi.schema("f1");
    expect(r.form_id).toBe("f1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/public-forms/f1/schema/");
    expect(init).toBeUndefined();
  });

  it("submits a payload", async () => {
    fetchMock.mockResolvedValueOnce(res({ success: true }));
    await publicFormsApi.submit("f1", { name: "Ada", _hp: "" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/public-forms/f1/submit/");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ name: "Ada", _hp: "" });
  });
});
