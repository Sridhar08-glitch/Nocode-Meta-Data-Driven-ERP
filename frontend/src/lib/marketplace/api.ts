/**
 * Marketplace client (Phase F3.4) — browse + install/upgrade/uninstall/rollback over
 * `/api/v1/marketplace/` (backend Phase 1.25). Browse is public; install management is owner/admin.
 * Install maps to the manifest-apply pipeline server-side (entities/workflows/rules/reports).
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface Plugin {
  id: string;
  slug: string;
  name: string;
  tagline: string;
  description: string;
  category: string;
  status: string;
  publisher_name: string;
  is_official: boolean;
  latest_version: string;
  install_count: number;
  icon_url: string;
}
export interface PluginVersionRef {
  id: string;
  plugin_id: string;
  version: string;
  changelog: string;
  is_published: boolean;
  created_at: string;
}
export interface PluginDetail extends Plugin {
  versions: PluginVersionRef[];
}
export interface InstalledPlugin {
  id: string;
  plugin_id: string;
  plugin_version_id: string;
  plugin_slug: string;
  installed_version: string;
  status: string;
  created_entity_ids: string[];
  created_workflow_ids: string[];
  created_rule_ids: string[];
  created_report_ids: string[];
  error_message: string;
  installed_at?: string;
}

const M = "/api/v1/marketplace";

function query(params: { category?: string; search?: string }): string {
  const qs = new URLSearchParams();
  if (params.category) qs.set("category", params.category);
  if (params.search) qs.set("search", params.search);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export const marketplaceApi = {
  browse: (params: { category?: string; search?: string } = {}) => apiGet<{ results: Plugin[] }>(`${M}/plugins/${query(params)}`),
  detail: (id: string) => apiGet<PluginDetail>(`${M}/plugins/${id}/`),
  installed: () => apiGet<{ results: InstalledPlugin[] }>(`${M}/installed/`),
  install: (pluginId: string, versionId: string) => apiSend<InstalledPlugin>(`${M}/plugins/${pluginId}/install/`, "POST", { version_id: versionId }),
  uninstall: (installedId: string, hard = false) => apiSend<InstalledPlugin>(`${M}/installed/${installedId}/uninstall/`, "POST", { hard }),
  upgrade: (installedId: string, versionId: string) => apiSend<InstalledPlugin>(`${M}/installed/${installedId}/upgrade/`, "POST", { version_id: versionId }),
  rollback: (installedId: string) => apiSend<InstalledPlugin>(`${M}/installed/${installedId}/rollback/`, "POST"),
};
