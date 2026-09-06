/**
 * Backups + PITR client (Phase F3.4) — `/api/v1/backups/` (backend Phase 1.24). Admin only.
 * CRITICAL: a restore ALWAYS targets a workspace that DIFFERS from the source (never overwrite
 * production) — enforced server-side and guarded client-side. The confirmation token is returned
 * exactly ONCE on restore-job creation (only its hash is stored); confirm uses it.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type BackupType = "full" | "incremental" | "config_only";

export interface BackupJob {
  id: string;
  backup_type: BackupType;
  status: string;
  is_automatic: boolean;
  storage_backend: string;
  size_bytes: number;
  is_encrypted: boolean;
  entity_count: number;
  record_count: number;
  document_count: number;
  expires_at: string | null;
  error_message: string;
  created_at: string;
}

export type RestoreType = "full" | "pitr";
export interface RestoreJob {
  id: string;
  restore_type: RestoreType;
  backup_job_id: string | null;
  pitr_target_sequence: number | null;
  pitr_target_timestamp: string | null;
  target_workspace_id: string;
  target_workspace_slug: string;
  status: string;
  confirmed_at: string | null;
  error_message: string;
  created_at: string;
}
export interface RestoreCreated extends RestoreJob {
  /** shown ONCE — pass back to confirm */
  confirmation_token: string;
}
export interface RestoreWrite {
  restore_type: RestoreType;
  backup_job_id?: string;
  pitr_target_sequence?: number;
  pitr_target_timestamp?: string;
  target_workspace_id: string;
  target_workspace_slug: string;
}

export interface RetentionPolicy {
  id: string;
  entity_id: string | null;
  entity_slug: string;
  retain_days: number;
  action: string;
  anonymize_fields: string[];
  is_active: boolean;
  last_enforced_at: string | null;
}
export interface RetentionWrite {
  entity_id?: string;
  entity_slug?: string;
  retain_days: number;
  action: string;
  anonymize_fields?: string[];
}

export const BACKUP_TYPES: { value: BackupType; label: string }[] = [
  { value: "full", label: "Full" },
  { value: "incremental", label: "Incremental" },
  { value: "config_only", label: "Config only" },
];
export const RETENTION_ACTIONS: { value: string; label: string }[] = [
  { value: "soft_delete", label: "Soft delete" },
  { value: "hard_delete", label: "Hard delete" },
  { value: "anonymize", label: "Anonymize" },
  { value: "archive", label: "Archive" },
];

const B = "/api/v1/backups";

export const backupsApi = {
  listJobs: () => apiGet<{ results: BackupJob[] }>(`${B}/jobs/`),
  createJob: (backup_type: BackupType) => apiSend<BackupJob>(`${B}/jobs/`, "POST", { backup_type }),
  deleteJob: (id: string) => apiSend<{ deleted: boolean }>(`${B}/jobs/${id}/`, "DELETE"),

  createRestore: (data: RestoreWrite) => apiSend<RestoreCreated>(`${B}/restore-jobs/`, "POST", data),
  getRestore: (id: string) => apiGet<RestoreJob>(`${B}/restore-jobs/${id}/`),
  confirmRestore: (id: string, token: string) => apiSend<RestoreJob>(`${B}/restore-jobs/${id}/confirm/`, "POST", { token }),

  listRetention: () => apiGet<{ results: RetentionPolicy[] }>(`${B}/retention-policies/`),
  createRetention: (data: RetentionWrite) => apiSend<RetentionPolicy>(`${B}/retention-policies/`, "POST", data),
  deleteRetention: (id: string) => apiSend<null>(`${B}/retention-policies/${id}/`, "DELETE"),
};
