import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ results: [] })),
  apiSend: vi.fn(() => Promise.resolve({})),
  downloadFile: vi.fn(() => Promise.resolve()),
}));
import { apiGet, apiSend, downloadFile } from "@/lib/api/request";
import { documentTemplatesApi } from "./api";

beforeEach(() => { vi.mocked(apiGet).mockClear(); vi.mocked(apiSend).mockClear(); vi.mocked(downloadFile).mockClear(); });

describe("documentTemplatesApi", () => {
  it("CRUDs + renders a PDF by record id", () => {
    documentTemplatesApi.list();
    documentTemplatesApi.create({ name: "Invoice", slug: "invoice", entity_slug: "order" });
    documentTemplatesApi.renderPdf("d1", "rec-9", "invoice.pdf");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/templates/documents/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/templates/documents/", "POST", expect.objectContaining({ entity_slug: "order" }));
    expect(downloadFile).toHaveBeenCalledWith("/api/v1/templates/documents/d1/render/?record_id=rec-9", "invoice.pdf");
  });
});
