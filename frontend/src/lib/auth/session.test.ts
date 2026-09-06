import { beforeEach, describe, expect, it } from "vitest";

import { getAccessToken, getRefreshToken } from "@/lib/auth/token-store";

import { AUTH_COOKIE, applyOAuthTokens, applyTokenResponse, logout, useAuthStore } from "./session";

// A minimal RS256-shaped JWT (header.payload.sig) with user_id + email claims.
function fakeJwt(payload: object): string {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "");
  return `${b64({ alg: "RS256" })}.${b64(payload)}.sig`;
}

describe("session", () => {
  beforeEach(() => {
    logout(false);
  });

  it("applyTokenResponse stores tokens, user, and the presence cookie", () => {
    applyTokenResponse({
      access: "a1",
      refresh: "r1",
      user: { id: "u1", email: "a@b.com", full_name: "A B", mfa_enabled: false },
    });
    expect(getAccessToken()).toBe("a1");
    expect(getRefreshToken()).toBe("r1");
    expect(useAuthStore.getState().user?.email).toBe("a@b.com");
    expect(document.cookie).toContain(`${AUTH_COOKIE}=1`);
  });

  it("applyOAuthTokens derives a user from the JWT claims", () => {
    const ok = applyOAuthTokens(fakeJwt({ user_id: "u2", email: "x@y.com" }), "r2");
    expect(ok).toBe(true);
    expect(useAuthStore.getState().user?.id).toBe("u2");
    expect(getRefreshToken()).toBe("r2");
  });

  it("applyOAuthTokens rejects a token without user_id", () => {
    expect(applyOAuthTokens(fakeJwt({ email: "x@y.com" }), "r3")).toBe(false);
  });

  it("logout clears tokens, user and the cookie", () => {
    applyTokenResponse({
      access: "a1",
      refresh: "r1",
      user: { id: "u1", email: "a@b.com", full_name: "A B", mfa_enabled: false },
    });
    logout(false);
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(document.cookie).not.toContain(`${AUTH_COOKIE}=1`);
  });
});
