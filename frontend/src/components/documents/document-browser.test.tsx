import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DocumentFolder, DocumentItem } from "@/lib/documents/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const downloadUrl = vi.hoisted(() => vi.fn(() => Promise.resolve({ url: "/api/v1/documents/download/?sig=x", expires_in: 300 })));
vi.mock("@/lib/documents/api", () => ({
  documentsApi: { downloadUrl },
  resolveDownloadUrl: (u: string) => `http://api.test${u}`,
}));

const foldersQ = { isLoading: false, isError: false, data: { results: [] as DocumentFolder[], count: 0 } };
const docsQ = { isLoading: false, isError: false, data: { results: [] as DocumentItem[], count: 0 } };
const versionsQ = { isLoading: false, data: { results: [], count: 0 } };
const createFolder = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delFolder = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const upload = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const delDoc = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const uploadVersion = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const useDocuments = vi.fn((p?: unknown) => {
  void p;
  return docsQ;
});
vi.mock("@/lib/documents/hooks", () => ({
  useFolders: () => foldersQ,
  useDocuments: (p: unknown) => useDocuments(p),
  useCreateFolder: () => createFolder,
  useDeleteFolder: () => delFolder,
  useUploadDocument: () => upload,
  useDeleteDocument: () => delDoc,
  useDocumentVersions: () => versionsQ,
  useUploadVersion: () => uploadVersion,
}));

import { DocumentBrowser } from "./document-browser";

const doc = (over: Partial<DocumentItem> = {}): DocumentItem => ({
  id: "d1", folder_id: null, name: "report.pdf", description: "", mime_type: "application/pdf", extension: "pdf",
  size_bytes: 2048, status: "ready", av_clean: true, current_version: 1, entity_id: null, record_id: null,
  is_public: false, created_at: "", ...over,
});
const folder = (id: string, name: string, path: string): DocumentFolder => ({
  id, name, parent_id: null, path, is_system: false, created_at: "",
});

beforeEach(() => {
  foldersQ.data = { results: [], count: 0 };
  docsQ.data = { results: [], count: 0 };
  useDocuments.mockClear();
  for (const m of [createFolder, delFolder, upload, delDoc, uploadVersion]) m.mutateAsync.mockClear();
  downloadUrl.mockClear();
  vi.clearAllMocks();
  downloadUrl.mockResolvedValue({ url: "/api/v1/documents/download/?sig=x", expires_in: 300 });
});

describe("DocumentBrowser", () => {
  it("uploads a file into the selected folder", async () => {
    foldersQ.data = { results: [folder("fold1", "Contracts", "/contracts")], count: 1 };
    render(<DocumentBrowser />);
    fireEvent.click(screen.getByRole("button", { name: "Contracts" }));
    // re-queried scoped to the folder
    expect((useDocuments.mock.calls.at(-1) as unknown[])[0]).toEqual({ folder_id: "fold1" });
    const file = new File(["data"], "a.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Upload file"), { target: { files: [file] } });
    await waitFor(() => expect(upload.mutateAsync).toHaveBeenCalled());
    const form = (upload.mutateAsync.mock.calls[0] as unknown[])[0] as FormData;
    expect(form.get("file")).toBe(file);
    expect(form.get("folder_id")).toBe("fold1");
  });

  it("downloads via a signed URL", async () => {
    docsQ.data = { results: [doc()], count: 1 };
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    render(<DocumentBrowser />);
    fireEvent.click(screen.getByRole("button", { name: "Download report.pdf" }));
    await waitFor(() => expect(downloadUrl).toHaveBeenCalledWith("d1"));
    expect(open).toHaveBeenCalledWith("http://api.test/api/v1/documents/download/?sig=x", "_blank", "noopener");
    open.mockRestore();
  });

  it("deletes a document", async () => {
    docsQ.data = { results: [doc()], count: 1 };
    render(<DocumentBrowser />);
    fireEvent.click(screen.getByRole("button", { name: "Delete report.pdf" }));
    await waitFor(() => expect(delDoc.mutateAsync).toHaveBeenCalledWith("d1"));
  });

  it("blocks download of a quarantined file", () => {
    docsQ.data = { results: [doc({ av_clean: false })], count: 1 };
    render(<DocumentBrowser />);
    expect(screen.getByText("quarantined")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download report.pdf" })).toBeDisabled();
  });
});
