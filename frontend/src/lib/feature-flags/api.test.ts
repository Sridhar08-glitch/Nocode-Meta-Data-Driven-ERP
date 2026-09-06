import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve([])), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { featureFlagsApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("featureFlagsApi", () => {
  it("hits flag + override endpoints", () => {
    featureFlagsApi.list();
    featureFlagsApi.create({ key: "new_dash", enabled: true, rollout_percent: 50 });
    featureFlagsApi.update("f1", { enabled: false });
    featureFlagsApi.remove("f1");
    featureFlagsApi.listOverrides("f1");
    featureFlagsApi.createOverride("f1", { target_type: "role", target_id: "r1", enabled: true });
    featureFlagsApi.removeOverride("f1", "o1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/feature-flags/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/feature-flags/", "POST", expect.objectContaining({ key: "new_dash" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/feature-flags/f1/", "PATCH", { enabled: false });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/feature-flags/f1/", "DELETE");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/feature-flags/f1/overrides/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/feature-flags/f1/overrides/", "POST", expect.objectContaining({ target_type: "role" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/feature-flags/f1/overrides/o1/", "DELETE");
  });
});
