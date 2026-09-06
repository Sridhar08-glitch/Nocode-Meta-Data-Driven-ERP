import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/config", () => ({ API_BASE_URL: "http://api.test" }));
const authFetch = vi.fn();
vi.mock("@/lib/api/client", () => ({ authFetch: (...a: unknown[]) => authFetch(...a) }));

import { authApi } from "./api";

function res(body: unknown, status = 200): Response {
  return { ok: status < 400, status, text: () => Promise.resolve(JSON.stringify(body)) } as unknown as Response;
}
beforeEach(() => { authFetch.mockReset(); authFetch.mockResolvedValue(res({})); });
afterEach(() => vi.clearAllMocks());

describe("authApi MFA + passkey enrollment", () => {
  it("calls the right endpoints/methods", async () => {
    await authApi.mfaSetupInitiate();
    await authApi.mfaSetupConfirm("123456");
    await authApi.mfaDisable("pw");
    await authApi.passkeyRegisterBegin();
    await authApi.passkeyRegisterComplete({ credential: { id: "c" }, name: "Key" });
    await authApi.listPasskeys();
    await authApi.deletePasskey("cred-1");
    const calls = authFetch.mock.calls.map((c) => [c[0], (c[1] as RequestInit).method]);
    expect(calls).toContainEqual(["http://api.test/api/v1/auth/mfa/setup/initiate/", "POST"]);
    expect(calls).toContainEqual(["http://api.test/api/v1/auth/mfa/setup/confirm/", "POST"]);
    expect(calls).toContainEqual(["http://api.test/api/v1/auth/mfa/disable/", "POST"]);
    expect(calls).toContainEqual(["http://api.test/api/v1/auth/mfa/passkey/register/begin/", "POST"]);
    expect(calls).toContainEqual(["http://api.test/api/v1/auth/mfa/passkey/register/complete/", "POST"]);
    expect(calls).toContainEqual(["http://api.test/api/v1/auth/mfa/passkey/", "GET"]);
    expect(calls).toContainEqual(["http://api.test/api/v1/auth/mfa/passkey/cred-1/", "DELETE"]);
  });
});
