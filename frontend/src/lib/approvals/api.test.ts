import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { approvalsApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("approvalsApi", () => {
  it("CRUDs processes with a levels matrix", () => {
    approvalsApi.listProcesses();
    approvalsApi.createProcess({
      name: "Big deals",
      slug: "big-deals",
      entity_id: "e1",
      levels: [{ level: 1, approvers: [{ type: "role", value: "manager" }], quorum: "any", timeout_hours: 24, on_timeout: "escalate" }],
    });
    approvalsApi.updateProcess("p1", { is_active: false });
    approvalsApi.deleteProcess("p1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/approvals/processes/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/approvals/processes/", "POST", expect.objectContaining({ slug: "big-deals" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/approvals/processes/p1/", "PATCH", { is_active: false });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/approvals/processes/p1/", "DELETE");
  });

  it("lists requests, pending-for-me, and resolves them", () => {
    approvalsApi.listRequests({ status: "pending", pending_for_me: true });
    approvalsApi.pendingForMe();
    approvalsApi.approve("req1", "ok");
    approvalsApi.reject("req1", "no");
    approvalsApi.cancel("req1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/approvals/requests/?status=pending&pending_for_me=1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/approvals/requests/pending-for-me/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/approvals/requests/req1/approve/", "POST", { comment: "ok" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/approvals/requests/req1/reject/", "POST", { comment: "no" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/approvals/requests/req1/cancel/", "POST");
  });
});
