import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({})), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { studioApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("studioApi", () => {
  it("hits the application endpoints", () => {
    studioApi.listApps();
    studioApi.switcher();
    studioApi.createApp({ name: "Sales", slug: "sales" });
    studioApi.publishApp("a1");
    studioApi.deleteApp("a1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/applications/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/applications/switcher/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/applications/", "POST", expect.objectContaining({ slug: "sales" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/applications/a1/publish/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/applications/a1/", "DELETE");
  });

  it("hits home-layout + resolve endpoints", () => {
    studioApi.listHome();
    studioApi.resolveHome("a1");
    studioApi.resolveHome();
    studioApi.createHome({ name: "Default", scope: "workspace" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/home-layouts/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/home-layouts/resolve/?app=a1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/home-layouts/resolve/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/home-layouts/", "POST", expect.objectContaining({ scope: "workspace" }));
  });

  it("hits navigation + resolve endpoints", () => {
    studioApi.listNav();
    studioApi.resolveNav("a1");
    studioApi.createNav({ name: "Main", scope: "workspace" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/navigation/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/navigation/resolve/?app=a1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/navigation/", "POST", expect.objectContaining({ name: "Main" }));
  });
});
