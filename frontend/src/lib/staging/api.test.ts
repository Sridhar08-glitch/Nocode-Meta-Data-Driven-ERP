import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
  apiSend: vi.fn(() => Promise.resolve({})),
  apiUpload: vi.fn(() => Promise.resolve({ id: "j1" })),
}));
import { apiGet, apiSend, apiUpload } from "@/lib/api/request";
import { exportApi, importApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
  vi.mocked(apiUpload).mockClear();
});

describe("importApi", () => {
  it("uploads a multipart job with entity + strategy", () => {
    const file = new File(["a,b\n1,2"], "data.csv", { type: "text/csv" });
    importApi.create({ file, entity_slug: "deals", duplicate_strategy: "update" });
    expect(apiUpload).toHaveBeenCalledWith("/api/v1/import/jobs/", expect.any(FormData));
    const form = vi.mocked(apiUpload).mock.calls[0][1] as FormData;
    expect(form.get("entity_slug")).toBe("deals");
    expect(form.get("duplicate_strategy")).toBe("update");
    expect(form.get("file")).toBe(file);
  });
  it("sets mapping, previews, confirms, cancels", () => {
    importApi.setMapping("j1", { Name: "name", Email: null });
    importApi.preview("j1");
    importApi.rows("j1", "invalid");
    importApi.confirm("j1");
    importApi.cancel("j1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/import/jobs/j1/mapping/", "PATCH", { column_mapping: { Name: "name", Email: null } });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/import/jobs/j1/preview/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/import/jobs/j1/rows/?status=invalid");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/import/jobs/j1/confirm/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/import/jobs/j1/cancel/", "POST");
  });
});

describe("exportApi", () => {
  it("creates an export and resolves the signed download url", () => {
    exportApi.create({ entity_slug: "deals", format: "xlsx" });
    exportApi.downloadUrl("e1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/export/jobs/", "POST", { entity_slug: "deals", format: "xlsx" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/export/jobs/e1/download/");
  });
});
