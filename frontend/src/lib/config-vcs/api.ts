/**
 * Config VCS API (Phase F1.8) — Draft→Publish lives here: a "publish" is a commit that
 * snapshots the workspace's live config; rollback restores a snapshot (recording a new
 * commit). Hand-typed: the OpenAPI spec lists these endpoints with empty bodies.
 * All endpoints require owner/admin (403 otherwise).
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface ConfigCommit {
  sha: string;
  parent_sha: string | null;
  message: string;
  branch: string;
  author_id: string | null;
  created_at: string;
  diff?: ConfigDiff;
}

/** Per-kind change set; kinds: entities, fields, rules, roles, permissions. */
export interface ConfigDiffEntry {
  added: Record<string, unknown>[];
  removed: Record<string, unknown>[];
  modified: { before: Record<string, unknown>; after: Record<string, unknown> }[];
}
export type ConfigDiff = Record<string, ConfigDiffEntry>;

export const configVcsApi = {
  /** Publish: snapshot live config as a commit. 400 if nothing changed. */
  commit: (message: string, branch = "main") =>
    apiSend<ConfigCommit>("/api/v1/config-vcs/commit/", "POST", { message, branch }),
  commits: (branch = "main") =>
    apiGet<{ results: ConfigCommit[]; count: number }>(
      `/api/v1/config-vcs/commits/?branch=${encodeURIComponent(branch)}`,
    ),
  diff: (a: string, b: string) =>
    apiGet<ConfigDiff>(
      `/api/v1/config-vcs/diff/?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`,
    ),
  /** Restore config to a prior snapshot; records a new commit. */
  rollback: (sha: string) =>
    apiSend<ConfigCommit>("/api/v1/config-vcs/rollback/", "POST", { sha }),
};
