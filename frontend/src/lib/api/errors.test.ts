import { describe, expect, it } from "vitest";

import { ApiError, toApiError } from "./errors";

const resp = (status: number, headers: Record<string, string> = {}) => ({
  status,
  headers: new Headers(headers),
});

describe("toApiError", () => {
  it("extracts a top-level detail message", () => {
    const err = toApiError(resp(403), { detail: "Not permitted to read lead" });
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(403);
    expect(err.message).toBe("Not permitted to read lead");
  });

  it("maps DRF field errors", () => {
    const err = toApiError(resp(400), {
      email: ["Enter a valid email."],
      password: ["Too short."],
    });
    expect(err.fieldErrors.email).toEqual(["Enter a valid email."]);
    expect(err.fieldErrors.password).toEqual(["Too short."]);
    // message falls back to the first field error
    expect(err.message).toBe("Enter a valid email.");
  });

  it("surfaces 429 + Retry-After and X-RateLimit headers", () => {
    const err = toApiError(
      resp(429, { "Retry-After": "30", "X-RateLimit-Remaining": "0" }),
      { detail: "Too many requests." },
    );
    expect(err.isRateLimited).toBe(true);
    expect(err.retryAfter).toBe(30);
    expect(err.rateLimit["x-ratelimit-remaining"]).toBe("0");
  });

  it("handles a plain string body", () => {
    const err = toApiError(resp(500), "Server Error");
    expect(err.message).toBe("Server Error");
  });

  it("defaults the message when the body is empty", () => {
    const err = toApiError(resp(502), null);
    expect(err.message).toBe("API error 502");
    expect(err.fieldErrors).toEqual({});
  });
});
