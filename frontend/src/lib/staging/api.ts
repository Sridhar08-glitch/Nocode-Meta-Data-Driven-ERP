/**
 * Import/Export client (Phase F2.6) — the import wizard (`/api/v1/import/jobs/`) and export jobs
 * (`/api/v1/export/jobs/`). Import create is multipart; export download returns a signed `{url}`.
 */
import { apiGet, apiSend, apiUpload } from "@/lib/api/request";

export type ImportStatus =
  | "uploading"
  | "parsing"
  | "validating"
  | "awaiting_confirm"
  | "importing"
  | "completed"
  | "failed"
  | "cancelled";
export type DuplicateStrategy = "skip" | "update" | "error";

export interface ImportJob {
  id: string;
  entity_id: string;
  entity_slug: string;
  status: ImportStatus;
  source_filename: string;
  column_mapping: Record<string, string | null>;
  duplicate_strategy: DuplicateStrategy;
  match_field_slug: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  imported_rows: number;
  skipped_rows: number;
  error_rows: number;
  error_message: string;
  created_at: string;
  updated_at: string;
}
export interface ImportRowError {
  field: string;
  message: string;
}
export interface ImportRow {
  id: string;
  row_number: number;
  raw_data: Record<string, string>;
  mapped_data: Record<string, unknown>;
  validation_errors: ImportRowError[];
  status: "pending" | "valid" | "invalid" | "imported" | "skipped" | "error";
  imported_record_id: string | null;
}

export type ExportFormat = "csv" | "xlsx" | "json";
export type ExportStatus = "queued" | "running" | "completed" | "failed";
export interface ExportJob {
  id: string;
  entity_id: string | null;
  status: ExportStatus;
  format: ExportFormat;
  output_filename: string;
  row_count: number;
  size_bytes: number;
  download_expires_at: string | null;
  error_message: string;
  created_at: string;
}
export interface Paged<T> {
  results: T[];
  count: number;
}

export const DUPLICATE_STRATEGY_OPTIONS: { value: DuplicateStrategy; label: string }[] = [
  { value: "skip", label: "Skip duplicates" },
  { value: "update", label: "Update duplicates" },
  { value: "error", label: "Error on duplicate" },
];
export const EXPORT_FORMAT_OPTIONS: { value: ExportFormat; label: string }[] = [
  { value: "csv", label: "CSV" },
  { value: "xlsx", label: "Excel (XLSX)" },
  { value: "json", label: "JSON" },
];

export const importApi = {
  list: () => apiGet<Paged<ImportJob>>("/api/v1/import/jobs/"),
  get: (id: string) => apiGet<ImportJob>(`/api/v1/import/jobs/${id}/`),
  create: (opts: { file: File; entity_slug: string; duplicate_strategy?: DuplicateStrategy }) => {
    const form = new FormData();
    form.set("file", opts.file);
    form.set("entity_slug", opts.entity_slug);
    if (opts.duplicate_strategy) form.set("duplicate_strategy", opts.duplicate_strategy);
    return apiUpload<ImportJob>("/api/v1/import/jobs/", form);
  },
  setMapping: (id: string, mapping: Record<string, string | null>) =>
    apiSend<ImportJob>(`/api/v1/import/jobs/${id}/mapping/`, "PATCH", { column_mapping: mapping }),
  preview: (id: string) => apiGet<{ results: ImportRow[] }>(`/api/v1/import/jobs/${id}/preview/`),
  rows: (id: string, status?: string) =>
    apiGet<Paged<ImportRow>>(`/api/v1/import/jobs/${id}/rows/${status ? `?status=${status}` : ""}`),
  confirm: (id: string) => apiSend<ImportJob>(`/api/v1/import/jobs/${id}/confirm/`, "POST"),
  cancel: (id: string) => apiSend<ImportJob>(`/api/v1/import/jobs/${id}/cancel/`, "POST"),
};

export const exportApi = {
  list: () => apiGet<Paged<ExportJob>>("/api/v1/export/jobs/"),
  get: (id: string) => apiGet<ExportJob>(`/api/v1/export/jobs/${id}/`),
  create: (data: { entity_slug?: string; nql_ast?: Record<string, unknown>; format?: ExportFormat; include_fields?: string[] }) =>
    apiSend<ExportJob>("/api/v1/export/jobs/", "POST", data),
  downloadUrl: (id: string) => apiGet<{ url: string }>(`/api/v1/export/jobs/${id}/download/`),
};
