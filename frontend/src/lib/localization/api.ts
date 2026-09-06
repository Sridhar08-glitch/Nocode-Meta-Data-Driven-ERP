/**
 * Localization admin client (Phase F3.1) — locale defaults + entity-label translations over
 * `/api/v1/localization/` (backend Phase 1.23). Locale validation (BCP-47 / zoneinfo / ISO-4217) is
 * server-side. Per-key translation overrides exist server-side too but aren't surfaced here yet.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface WorkspaceLocale {
  id?: string;
  default_locale: string;
  default_timezone: string;
  default_currency: string;
  enabled_locales: string[];
  date_format?: string;
  time_format?: string;
}
export interface WorkspaceLocaleWrite {
  default_locale?: string;
  default_timezone?: string;
  default_currency?: string;
  enabled_locales?: string[];
}

export interface EntityLabel {
  id: string;
  entity_id: string | null;
  field_id: string | null;
  locale: string;
  singular: string;
  plural: string;
}
export interface EntityLabelWrite {
  entity_id?: string | null;
  field_id?: string | null;
  locale: string;
  singular: string;
  plural: string;
}
export interface Paged<T> {
  results: T[];
  count: number;
}

const L = "/api/v1/localization";

export const localizationApi = {
  getLocale: () => apiGet<WorkspaceLocale>(`${L}/locale/`),
  setLocale: (data: WorkspaceLocaleWrite) => apiSend<WorkspaceLocale>(`${L}/locale/`, "PATCH", data),
  listEntityLabels: () => apiGet<Paged<EntityLabel>>(`${L}/entity-labels/`),
  createEntityLabel: (data: EntityLabelWrite) => apiSend<EntityLabel>(`${L}/entity-labels/`, "POST", data),
  deleteEntityLabel: (id: string) => apiSend<null>(`${L}/entity-labels/${id}/`, "DELETE"),
};
