import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ ok: "get" })),
  apiSend: vi.fn(() => Promise.resolve({ ok: "send" })),
}));

import { apiGet, apiSend } from "@/lib/api/request";

import { personalizationApi } from "./api";

describe("personalizationApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("GET appearance hits /api/v1/me/appearance/", async () => {
    await personalizationApi.appearance();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/me/appearance/");
  });

  it("GET preferences hits /api/v1/me/preferences/", async () => {
    await personalizationApi.preferences();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/me/preferences/");
  });

  it("PUT preferences wraps values under { values }", async () => {
    await personalizationApi.savePreferences({ density: "compact" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/me/preferences/", "PUT", {
      values: { density: "compact" },
    });
  });

  it("reset with keys sends { keys }, without keys sends {}", async () => {
    await personalizationApi.resetPreferences(["density"]);
    expect(apiSend).toHaveBeenCalledWith("/api/v1/me/preferences/reset/", "POST", {
      keys: ["density"],
    });
    await personalizationApi.resetPreferences();
    expect(apiSend).toHaveBeenCalledWith("/api/v1/me/preferences/reset/", "POST", {});
  });
});
