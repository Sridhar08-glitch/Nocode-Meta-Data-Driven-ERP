/**
 * Business Process Catalog client (Phase F2.9) — browse/preview/install packaged process blueprints
 * over `/api/v1/process-catalog/` (backend Phase 1.34). Browse + preview = any member; install into
 * the workspace = owner/admin. Install maps to the marketplace apply pipeline server-side.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface ProcessBlueprint {
  id: string;
  name: string;
  slug: string;
  category: string;
  description: string;
  publisher: string;
  manifest: Record<string, unknown>;
  is_published: boolean;
  install_count: number;
  created_at: string;
  updated_at: string;
}

export interface BlueprintSummary {
  entities: number;
  workflows: number;
  rules: number;
  reports: number;
  notification_templates: number;
}
export interface BlueprintPreview {
  id: string;
  slug: string;
  name: string;
  valid: boolean;
  errors: string[];
  summary: BlueprintSummary;
  manifest: Record<string, unknown>;
}
export interface InstallResult {
  blueprint: string;
  entity_ids: string[];
  workflow_ids: string[];
  rule_ids: string[];
  report_ids: string[];
}
export interface Paged<T> {
  results: T[];
  count: number;
}

const P = "/api/v1/process-catalog";

function query(params: { category?: string; search?: string }): string {
  const qs = new URLSearchParams();
  if (params.category) qs.set("category", params.category);
  if (params.search) qs.set("search", params.search);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export const catalogApi = {
  list: (params: { category?: string; search?: string } = {}) =>
    apiGet<Paged<ProcessBlueprint>>(`${P}/${query(params)}`),
  preview: (id: string) => apiGet<BlueprintPreview>(`${P}/${id}/`),
  install: (id: string) => apiSend<InstallResult>(`${P}/${id}/install/`, "POST"),
};
