import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [] })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { integrationsApi } from "./api";

beforeEach(() => { vi.mocked(apiGet).mockClear(); vi.mocked(apiSend).mockClear(); });

describe("integrationsApi", () => {
  it("covers webhook subscription endpoints", () => {
    integrationsApi.listSubs();
    integrationsApi.createSub({ name: "x", target_url: "https://e.com", event_types: ["record.created"] });
    integrationsApi.testSub("s1");
    integrationsApi.deliveries("s1");
    integrationsApi.enableSub("s1");
    integrationsApi.disableSub("s1");
    integrationsApi.deleteSub("s1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/integrations/webhooks/subscriptions/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/integrations/webhooks/subscriptions/", "POST", expect.objectContaining({ target_url: "https://e.com" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/integrations/webhooks/subscriptions/s1/test/", "POST");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/integrations/webhooks/subscriptions/s1/deliveries/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/integrations/webhooks/subscriptions/s1/enable/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/integrations/webhooks/subscriptions/s1/disable/", "POST");
  });
  it("covers inbound, connector, and oauth endpoints", () => {
    integrationsApi.createInbound({ name: "n", slug: "n" });
    integrationsApi.rotateInbound("i1");
    integrationsApi.createConnector({ name: "c", slug: "c", base_url: "https://api.e.com" });
    integrationsApi.testConnector("c1");
    integrationsApi.createOAuth({ name: "o", provider: "google", client_id: "cid" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/integrations/inbound-webhooks/", "POST", expect.objectContaining({ slug: "n" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/integrations/inbound-webhooks/i1/rotate-token/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/integrations/connectors/", "POST", expect.objectContaining({ base_url: "https://api.e.com" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/integrations/connectors/c1/test/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/integrations/oauth-apps/", "POST", expect.objectContaining({ provider: "google" }));
  });
});
