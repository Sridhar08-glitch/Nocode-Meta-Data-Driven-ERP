import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/config", () => ({ API_BASE_URL: "http://api.test" }));
vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ results: [] })),
  apiSend: vi.fn(() => Promise.resolve({})),
  apiUpload: vi.fn(() => Promise.resolve({})),
}));
import { apiGet, apiSend, apiUpload } from "@/lib/api/request";
import { documentsApi, resolveDownloadUrl } from "./api";

beforeEach(() => { vi.mocked(apiGet).mockClear(); vi.mocked(apiSend).mockClear(); vi.mocked(apiUpload).mockClear(); });

describe("documentsApi", () => {
  it("hits folder + document + version endpoints", () => {
    documentsApi.listFolders();
    documentsApi.createFolder({ name: "Contracts", parent_id: null });
    documentsApi.list({ folder_id: "f1" });
    documentsApi.upload(new FormData());
    documentsApi.downloadUrl("d1");
    documentsApi.versions("d1");
    documentsApi.uploadVersion("d1", new FormData());
    documentsApi.remove("d1");
    documentsApi.attach("d1", { record_id: "r1", entity_id: "e1" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/documents/folders/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/documents/folders/", "POST", { name: "Contracts", parent_id: null });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/documents/?folder_id=f1");
    expect(apiUpload).toHaveBeenCalledWith("/api/v1/documents/", expect.any(FormData));
    expect(apiGet).toHaveBeenCalledWith("/api/v1/documents/d1/download-url/");
    expect(apiUpload).toHaveBeenCalledWith("/api/v1/documents/d1/versions/", expect.any(FormData));
    expect(apiSend).toHaveBeenCalledWith("/api/v1/documents/d1/", "DELETE");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/documents/d1/attach/", "POST", { record_id: "r1", entity_id: "e1" });
  });
  it("resolves relative signed URLs to absolute, leaves absolute alone", () => {
    expect(resolveDownloadUrl("/api/v1/documents/download/?sig=x")).toBe("http://api.test/api/v1/documents/download/?sig=x");
    expect(resolveDownloadUrl("https://s3.example.com/x")).toBe("https://s3.example.com/x");
  });
});
