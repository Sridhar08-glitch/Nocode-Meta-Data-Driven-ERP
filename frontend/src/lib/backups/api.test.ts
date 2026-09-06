import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [] })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { backupsApi } from "./api";

beforeEach(() => { vi.mocked(apiGet).mockClear(); vi.mocked(apiSend).mockClear(); });

describe("backupsApi", () => {
  it("manages jobs, restores, and retention", () => {
    backupsApi.listJobs();
    backupsApi.createJob("full");
    backupsApi.deleteJob("j1");
    backupsApi.createRestore({ restore_type: "pitr", pitr_target_sequence: 42, target_workspace_id: "w2", target_workspace_slug: "sandbox" });
    backupsApi.confirmRestore("r1", "tok");
    backupsApi.createRetention({ entity_slug: "lead", retain_days: 30, action: "soft_delete" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/backups/jobs/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/backups/jobs/", "POST", { backup_type: "full" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/backups/jobs/j1/", "DELETE");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/backups/restore-jobs/", "POST", expect.objectContaining({ restore_type: "pitr", target_workspace_id: "w2" }));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/backups/restore-jobs/r1/confirm/", "POST", { token: "tok" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/backups/retention-policies/", "POST", expect.objectContaining({ retain_days: 30 }));
  });
});
