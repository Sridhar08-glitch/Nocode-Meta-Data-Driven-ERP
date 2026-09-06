import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
  apiSend: vi.fn(() => Promise.resolve({})),
}));
import { apiSend } from "@/lib/api/request";
import { crmApi } from "./api";

beforeEach(() => {
  vi.mocked(apiSend).mockClear();
});

describe("crmApi", () => {
  it("runs setup and creates numbered documents", () => {
    crmApi.setup();
    crmApi.createDocument("lead", { name: "Acme", email: "a@b.co" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/crm/setup/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/crm/lead/", "POST", { name: "Acme", email: "a@b.co" });
  });

  it("qualifies a lead, creating a linked opportunity", () => {
    crmApi.qualifyLead("lead-1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/crm/leads/lead-1/qualify/", "POST");
  });

  it("wins and loses an opportunity with a reason", () => {
    crmApi.winOpportunity("opp-1", "Closed at list price");
    crmApi.loseOpportunity("opp-2", "Went with competitor");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/crm/opportunities/opp-1/win/", "POST", { reason: "Closed at list price" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/crm/opportunities/opp-2/lose/", "POST", { reason: "Went with competitor" });
  });

  it("completes an activity", () => {
    crmApi.completeActivity("act-1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/crm/activities/act-1/complete/", "POST");
  });
});
