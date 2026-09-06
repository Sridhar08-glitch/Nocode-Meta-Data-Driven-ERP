import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DocumentTemplate } from "@/lib/document-templates/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => ({ data: [{ id: "e1", name: "Orders", slug: "order" }] }) }));

const listQ = { isLoading: false, isError: false, data: { results: [] as DocumentTemplate[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
const renderPdf = { mutateAsync: vi.fn(() => Promise.resolve()), isPending: false };
vi.mock("@/lib/document-templates/hooks", () => ({
  useDocumentTemplates: () => listQ,
  useCreateDocTemplate: () => create,
  useUpdateDocTemplate: () => update,
  useDeleteDocTemplate: () => del,
  useRenderDocPdf: () => renderPdf,
}));

import { DocumentTemplateBuilder } from "./document-template-builder";

const tpl = (over: Partial<DocumentTemplate> = {}): DocumentTemplate => ({
  id: "d1", name: "Invoice", slug: "invoice", entity_slug: "order", page_config: {}, blocks: [{ field: "total" }],
  line_items: {}, version: 1, is_active: true, created_at: "", updated_at: "", ...over,
});

beforeEach(() => {
  listQ.data = { results: [], count: 0 };
  for (const m of [create, update, del, renderPdf]) m.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("DocumentTemplateBuilder", () => {
  it("creates an entity-bound template with header fields", async () => {
    render(<DocumentTemplateBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New template" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Invoice" } });
    fireEvent.click(screen.getByRole("combobox", { name: "Bound entity" }));
    fireEvent.click(await screen.findByRole("option", { name: "Orders" }));
    fireEvent.change(screen.getByLabelText("Field 1 slug"), { target: { value: "total" } });
    fireEvent.click(screen.getByRole("button", { name: "Create template" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ slug: "invoice", entity_slug: "order", blocks: [{ field: "total", label: undefined }] }),
    );
  });

  it("renders a record to PDF by id", async () => {
    listQ.data = { results: [tpl()], count: 1 };
    render(<DocumentTemplateBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Render Invoice" }));
    fireEvent.change(screen.getByLabelText(/Record ID/), { target: { value: "rec-42" } });
    fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
    await waitFor(() => expect(renderPdf.mutateAsync).toHaveBeenCalledWith({ id: "d1", recordId: "rec-42", filename: "invoice.pdf" }));
  });
});
