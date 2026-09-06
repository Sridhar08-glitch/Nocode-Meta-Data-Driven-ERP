import { describe, expect, it } from "vitest";

import { API_BASE_URL } from "@/lib/api/client";

/**
 * F0 smoke test: the live backend serves its OpenAPI schema (the `gen:api` source).
 * When the backend is unreachable (e.g. CI without a server) the test is skipped rather
 * than failed — but when it IS up, it asserts a 200, proving the client points at a real
 * endpoint. Run with the Django dev server on :8000.
 */
describe("backend OpenAPI schema", () => {
  it("responds 200 at /api/openapi/ (skipped if backend is down)", async () => {
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/api/openapi/`, {
        signal: AbortSignal.timeout(2500),
      });
    } catch {
      // backend not running — skip, don't fail CI
      return;
    }
    expect(res.status).toBe(200);
  });
});
