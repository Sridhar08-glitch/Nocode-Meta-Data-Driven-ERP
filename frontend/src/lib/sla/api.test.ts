import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { slaApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("slaApi", () => {
  it("CRUDs policies with targets", () => {
    slaApi.listPolicies();
    slaApi.createPolicy({ name: "Support", slug: "support", entity_id: "e1", targets: [{ metric: "resolution", target_minutes: 480, warning_at_percent: 75, business_hours_only: true }] });
    slaApi.updatePolicy("p1", { is_active: false });
    slaApi.deletePolicy("p1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/sla/policies/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/sla/policies/", "POST", expect.objectContaining({ slug: "support" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/sla/policies/p1/", "PATCH", { is_active: false });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/sla/policies/p1/", "DELETE");
  });

  it("manages business hours (no delete) + dashboard", () => {
    slaApi.listBusinessHours();
    slaApi.createBusinessHours({ name: "EU", timezone: "Europe/Paris", weekly_hours: { mon: [{ start: "09:00", end: "17:00" }] } });
    slaApi.updateBusinessHours("b1", { region: "EMEA" });
    slaApi.dashboard();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/sla/business-hours/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/sla/business-hours/", "POST", expect.objectContaining({ timezone: "Europe/Paris" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/sla/business-hours/b1/", "PATCH", { region: "EMEA" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/sla/dashboard/");
  });

  it("reads + pauses + resumes per-record SLA", () => {
    slaApi.recordStatus("tickets", "rec1");
    slaApi.pause("tickets", "rec1");
    slaApi.resume("tickets", "rec1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/data/tickets/rec1/sla/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/tickets/rec1/sla/pause/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/data/tickets/rec1/sla/resume/", "POST");
  });
});
