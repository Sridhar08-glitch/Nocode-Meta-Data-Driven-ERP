/**
 * Document/PDF Template client (Phase F3.6) — `/api/v1/templates/documents/` (backend Phase 1.33).
 * A template binds to an `entity_slug`; `render/?record_id=` returns a PDF (rendered server-side via
 * the pluggable reporting PDF backend). Reads = member; writes = admin.
 */
import { apiGet, apiSend, downloadFile } from "@/lib/api/request";

export interface DocBlock {
  field: string;
  label?: string;
}
export interface DocLineItems {
  entity_slug?: string;
  relation_field?: string;
  columns?: string[];
  title?: string;
}
export interface DocPageConfig {
  title?: string;
  subtitle?: string;
  watermark?: string;
}
export interface DocumentTemplate {
  id: string;
  name: string;
  slug: string;
  entity_slug: string;
  page_config: DocPageConfig;
  blocks: DocBlock[];
  line_items: DocLineItems;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
export interface DocumentTemplateWrite {
  name: string;
  slug: string;
  entity_slug: string;
  page_config?: DocPageConfig;
  blocks?: DocBlock[];
  line_items?: DocLineItems;
}

const D = "/api/v1/templates/documents";

export const documentTemplatesApi = {
  list: () => apiGet<{ results: DocumentTemplate[]; count: number }>(`${D}/`),
  create: (data: DocumentTemplateWrite) => apiSend<DocumentTemplate>(`${D}/`, "POST", data),
  update: (id: string, data: Partial<DocumentTemplateWrite>) => apiSend<DocumentTemplate>(`${D}/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<null>(`${D}/${id}/`, "DELETE"),
  renderPdf: (id: string, recordId: string, filename: string) =>
    downloadFile(`${D}/${id}/render/?record_id=${encodeURIComponent(recordId)}`, filename),
};
