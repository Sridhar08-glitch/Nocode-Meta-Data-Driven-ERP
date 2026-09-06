/**
 * Solution Template Framework client (Phase P2.4A) — browse/preview/install curated end-to-end
 * solution templates over `/api/v1/solution-templates/` (backend live). Browse + preview + library +
 * installed list = any member; install + uninstall into the workspace = owner/admin. Install maps to
 * the marketplace apply pipeline server-side (entities/forms/views/workflows/rules/reports/…).
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface TemplateSummary {
  entities: number;
  forms: number;
  views: number;
  workflows: number;
  rules: number;
  reports: number;
  roles: number;
  dashboards: number;
  applications: number;
}

export interface SolutionTemplate {
  id: string;
  name: string;
  slug: string;
  category: string;
  description: string;
  publisher: string;
  icon: string;
  color: string;
  version: string;
  is_system: boolean;
  is_published: boolean;
  install_count: number;
  summary: TemplateSummary;
  created_at: string;
}

export interface PreviewSummary {
  entities: number;
  forms: number;
  views: number;
  workflows: number;
  rules: number;
  reports: number;
  notification_templates: number;
  roles: number;
  dashboards: number;
  applications: number;
  navigations: number;
  home_layouts: number;
}

export interface TemplatePreview {
  id: string;
  slug: string;
  name: string;
  category: string;
  version: string;
  valid: boolean;
  errors: string[];
  summary: PreviewSummary;
  manifest: Record<string, unknown>;
}

export interface InstalledSolution {
  id: string;
  solution_template_id: string;
  solution_slug: string;
  solution_name: string;
  installed_version: string;
  status: string;
  summary: TemplateSummary;
  created_entity_ids: string[];
  created_application_ids: string[];
  created_at: string;
}

export interface LibraryObject {
  slug: string;
  name: string;
  plural_name?: string;
  fields?: unknown[];
}
export interface SolutionLibrary {
  business_objects: LibraryObject[];
  workflows: LibraryObject[];
  roles: LibraryObject[];
  dashboards: LibraryObject[];
  reports: LibraryObject[];
}

export interface Paged<T> {
  results: T[];
  count: number;
}

/**
 * The solution-template list endpoints (`/` browse and `/installed/`) are DRF
 * APIViews that return a bare JSON array, not a paginated `{results,count}`
 * envelope. Consumers (catalog browse/installed tabs + every module
 * install-gate) rely on `.results`, so normalise both shapes here.
 */
function asPaged<T>(data: T[] | Paged<T>): Paged<T> {
  return Array.isArray(data) ? { results: data, count: data.length } : data;
}

/* ------------------------------------------------------------------ *
 * Create Solution Wizard (Phase P2.4B) — compose a solution from
 * library building blocks, preview the resolved manifest, then install.
 * Backend: `/api/v1/solution-templates/wizard/*`. options/preview/resolve
 * are member-readable; create is owner/admin only (API enforces).
 * ------------------------------------------------------------------ */

/** Library block keys a solution_type / industry recommends pre-selecting. */
export interface WizardRecommends {
  business_objects: string[];
  workflows: string[];
  roles: string[];
  dashboards: string[];
  reports: string[];
}
export interface WizardChoice {
  key: string;
  label: string;
  recommends: WizardRecommends;
}
/** Full pickable set, sourced once from the backend (single source of truth). */
export interface WizardLibrary {
  business_objects: LibraryObject[];
  workflows: LibraryObject[];
  roles: LibraryObject[];
  dashboards: LibraryObject[];
  reports: LibraryObject[];
}
export interface WizardOptions {
  solution_types: WizardChoice[];
  industries: WizardChoice[];
  library: WizardLibrary;
}

export interface WizardConfig {
  solution_name: string;
  application_name: string;
  description: string;
  icon: string;
  color: string;
}

/** The POST body shared by /preview/ and /create/. */
export interface WizardSelection {
  solution_type: string;
  industry: string | null;
  business_objects: string[];
  workflows: string[];
  roles: string[];
  dashboards: string[];
  reports: string[];
  config: WizardConfig;
}

export interface WizardPreview {
  valid: boolean;
  errors: string[];
  warnings: string[];
  resolved_objects: string[];
  summary: PreviewSummary;
  manifest: Record<string, unknown>;
}

export interface ResolvedDependencies {
  resolved_objects: string[];
}

const S = "/api/v1/solution-templates";
const W = `${S}/wizard`;

function query(params: { category?: string; search?: string }): string {
  const qs = new URLSearchParams();
  if (params.category) qs.set("category", params.category);
  if (params.search) qs.set("search", params.search);
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export const solutionTemplatesApi = {
  list: (params: { category?: string; search?: string } = {}) =>
    apiGet<SolutionTemplate[] | Paged<SolutionTemplate>>(`${S}/${query(params)}`).then(asPaged),
  library: () => apiGet<SolutionLibrary>(`${S}/library/`),
  preview: (id: string) => apiGet<TemplatePreview>(`${S}/${id}/`),
  install: (id: string) => apiSend<InstalledSolution>(`${S}/${id}/install/`, "POST"),
  installed: () =>
    apiGet<InstalledSolution[] | Paged<InstalledSolution>>(`${S}/installed/`).then(asPaged),
  uninstall: (installedId: string, hard = false) =>
    apiSend<InstalledSolution>(`${S}/installed/${installedId}/uninstall/`, "POST", { hard }),

  // Create Solution Wizard (P2.4B)
  wizardOptions: () => apiGet<WizardOptions>(`${W}/options/`),
  resolveDependencies: (businessObjects: string[]) =>
    apiSend<ResolvedDependencies>(`${W}/resolve/`, "POST", { business_objects: businessObjects }),
  previewSolution: (selection: WizardSelection) =>
    apiSend<WizardPreview>(`${W}/preview/`, "POST", selection),
  createSolution: (selection: WizardSelection) =>
    apiSend<InstalledSolution>(`${W}/create/`, "POST", selection),
};
