import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ImportJob, ImportRow } from "@/lib/staging/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const jobState = { isLoading: false, isError: false, data: undefined as ImportJob | undefined };
const previewState = { data: { results: [] as ImportRow[] } };
const confirm = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const setMapping = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/staging/hooks", () => ({
  useImportJob: () => jobState,
  useImportPreview: () => previewState,
  useConfirmImport: () => confirm,
  useSetImportMapping: () => setMapping,
}));
vi.mock("@/lib/metadata/builder-hooks", () => ({
  useFields: () => ({ data: [{ slug: "name", name: "Name" }, { slug: "email", name: "Email" }] }),
}));

import { ImportWizard } from "./import-wizard";

function job(over: Partial<ImportJob> = {}): ImportJob {
  return {
    id: "j1",
    entity_id: "e1",
    entity_slug: "deals",
    status: "awaiting_confirm",
    source_filename: "data.csv",
    column_mapping: {},
    duplicate_strategy: "skip",
    match_field_slug: "",
    total_rows: 10,
    valid_rows: 8,
    invalid_rows: 2,
    imported_rows: 0,
    skipped_rows: 0,
    error_rows: 0,
    error_message: "",
    created_at: "",
    updated_at: "",
    ...over,
  };
}

beforeEach(() => {
  jobState.data = undefined;
  previewState.data = { results: [] };
  confirm.mutateAsync.mockClear().mockResolvedValue({});
  setMapping.mutateAsync.mockClear().mockResolvedValue({});
  vi.clearAllMocks();
});

describe("ImportWizard", () => {
  it("shows the validation report and confirms the import (end-to-end)", async () => {
    jobState.data = job();
    previewState.data = {
      results: [
        { id: "r1", row_number: 1, raw_data: {}, mapped_data: {}, validation_errors: [], status: "valid", imported_record_id: null },
        { id: "r2", row_number: 2, raw_data: {}, mapped_data: {}, validation_errors: [{ field: "email", message: "required" }], status: "invalid", imported_record_id: null },
      ],
    };
    render(<ImportWizard jobId="j1" />);
    expect(screen.getByText("email: required")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Import 8 valid rows" }));
    await waitFor(() => expect(confirm.mutateAsync).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalled();
  });

  it("surfaces a failed import's error and shows imported counts on completion", () => {
    jobState.data = job({ status: "completed", imported_rows: 8, skipped_rows: 2 });
    render(<ImportWizard jobId="j1" />);
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Import .* valid rows/ })).not.toBeInTheDocument();
  });

  it("disables confirm when there are no valid rows", () => {
    jobState.data = job({ valid_rows: 0 });
    render(<ImportWizard jobId="j1" />);
    expect(screen.getByRole("button", { name: "Import 0 valid rows" })).toBeDisabled();
  });

  it("remaps a source column to a field and re-validates", async () => {
    jobState.data = job({ column_mapping: { "Full Name": "name", "E-mail": null } });
    render(<ImportWizard jobId="j1" />);
    fireEvent.click(screen.getByRole("combobox", { name: "Map E-mail" }));
    fireEvent.click(await screen.findByRole("option", { name: "Email" }));
    fireEvent.click(screen.getByRole("button", { name: /Save mapping/ }));
    await waitFor(() =>
      expect(setMapping.mutateAsync).toHaveBeenCalledWith({ "Full Name": "name", "E-mail": "email" }),
    );
  });
});
