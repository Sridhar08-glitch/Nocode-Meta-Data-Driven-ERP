import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({})),
  apiSend: vi.fn(() => Promise.resolve({})),
}));
import { apiSend } from "@/lib/api/request";
import { hrApi } from "./api";

beforeEach(() => {
  vi.mocked(apiSend).mockClear();
});

describe("hrApi", () => {
  it("hits the native HR lifecycle endpoints with the right payloads", () => {
    hrApi.setup();
    hrApi.createDocument("candidate", { full_name: "Ada" });
    hrApi.hireCandidate("c1");
    hrApi.completeInterview("i1");
    hrApi.acceptOffer("o1");
    hrApi.approveLeave("lr1");
    hrApi.rejectLeave("lr2");
    hrApi.completePerformance("pr1");
    hrApi.promoteEmployee("e1", "pos9");
    hrApi.transferEmployee("e1", "dep4");
    hrApi.offboardEmployee("e1");

    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/setup/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/candidate/", "POST", { full_name: "Ada" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/candidates/c1/hire/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/interviews/i1/complete/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/offers/o1/accept/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/leave-requests/lr1/approve/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/leave-requests/lr2/reject/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/performance-reviews/pr1/complete/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/employees/e1/promote/", "POST", { new_position: "pos9" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/employees/e1/transfer/", "POST", { new_department: "dep4" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/hr/employees/e1/offboard/", "POST");
  });
});
