/**
 * Documents client (Phase F3/P1.2) — folders + documents over `/api/v1/documents/` (backend
 * Phase 1.15). Uploads are multipart (`apiUpload`); downloads go through a short-lived SIGNED URL
 * (the raw storage key is never exposed). Workspace-scoped + RBAC server-side.
 */
import { apiGet, apiSend, apiUpload } from "@/lib/api/request";
import { API_BASE_URL } from "@/lib/api/config";

export interface DocumentFolder {
  id: string;
  name: string;
  parent_id: string | null;
  path: string;
  is_system: boolean;
  created_at: string;
}
export interface DocumentItem {
  id: string;
  folder_id: string | null;
  name: string;
  description: string;
  mime_type: string;
  extension: string;
  size_bytes: number;
  status: string;
  av_clean: boolean | null;
  current_version: number;
  entity_id: string | null;
  record_id: string | null;
  is_public: boolean;
  created_at: string;
}
export interface DocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  size_bytes: number;
  uploaded_by: string | null;
  comment: string;
  created_at: string;
}
export interface DocListParams {
  folder_id?: string | null;
  record_id?: string;
  entity_id?: string;
}

function listQuery(p: DocListParams): string {
  const qs = new URLSearchParams();
  if (p.folder_id) qs.set("folder_id", p.folder_id);
  if (p.record_id) qs.set("record_id", p.record_id);
  if (p.entity_id) qs.set("entity_id", p.entity_id);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

/** Resolve a signed download URL (relative local-signed or absolute S3-presigned) to absolute. */
export function resolveDownloadUrl(url: string): string {
  return /^https?:\/\//.test(url) ? url : `${API_BASE_URL}${url}`;
}

const D = "/api/v1/documents";

export const documentsApi = {
  listFolders: () => apiGet<{ results: DocumentFolder[]; count: number }>(`${D}/folders/`),
  createFolder: (data: { name: string; parent_id?: string | null }) => apiSend<DocumentFolder>(`${D}/folders/`, "POST", data),
  deleteFolder: (id: string) => apiSend<null>(`${D}/folders/${id}/`, "DELETE"),

  list: (params: DocListParams = {}) => apiGet<{ results: DocumentItem[]; count: number }>(`${D}/${listQuery(params)}`),
  upload: (form: FormData) => apiUpload<DocumentItem>(`${D}/`, form),
  patch: (id: string, data: { name?: string; description?: string; folder_id?: string | null; is_public?: boolean }) =>
    apiSend<DocumentItem>(`${D}/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<null>(`${D}/${id}/`, "DELETE"),
  restore: (id: string) => apiSend<DocumentItem>(`${D}/${id}/restore/`, "POST"),
  downloadUrl: (id: string) => apiGet<{ url: string; expires_in: number }>(`${D}/${id}/download-url/`),
  versions: (id: string) => apiGet<{ results: DocumentVersion[]; count: number }>(`${D}/${id}/versions/`),
  uploadVersion: (id: string, form: FormData) => apiUpload<DocumentItem>(`${D}/${id}/versions/`, form),
  attach: (id: string, data: { record_id: string; entity_id?: string }) => apiSend<DocumentItem>(`${D}/${id}/attach/`, "POST", data),
  detach: (id: string) => apiSend<DocumentItem>(`${D}/${id}/detach/`, "POST"),
};
