import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [] })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { recycleBinApi } from "./api";

beforeEach(() => { vi.mocked(apiGet).mockClear(); vi.mocked(apiSend).mockClear(); });

describe("recycleBinApi", () => {
  it("lists (filtered), restores, purges, and bulk-acts", () => {
    recycleBinApi.list({ entity_slug: "lead", include_purged: true });
    recycleBinApi.restore("e1");
    recycleBinApi.purge("e1");
    recycleBinApi.bulkRestore(["a", "b"]);
    recycleBinApi.bulkPurge(["a"]);
    expect(apiGet).toHaveBeenCalledWith("/api/v1/recyclebin/?entity_slug=lead&include_purged=1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/recyclebin/e1/restore/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/recyclebin/e1/purge/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/recyclebin/bulk-restore/", "POST", { entry_ids: ["a", "b"] });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/recyclebin/bulk-purge/", "POST", { entry_ids: ["a"] });
  });
});
