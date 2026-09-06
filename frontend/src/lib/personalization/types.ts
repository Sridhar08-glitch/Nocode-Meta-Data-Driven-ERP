import type { EffectiveAppearance } from "@/lib/branding/apply";

/** GET /api/v1/me/appearance/ — the resolved effective appearance + lock metadata. */
export interface AppearanceResponse {
  appearance: EffectiveAppearance;
  locked: string[];
  sources: Record<string, string>;
  allow_theme_toggle: boolean;
}

/** One entry of the preference registry catalogue (drives the Appearance page controls). */
export interface PreferenceCatalogueEntry {
  type: string;
  values: string[] | null;
  min: number | null;
  max: number | null;
  default: unknown;
  lockable: boolean;
  accessibility: boolean;
}

/** GET/PUT /api/v1/me/preferences/ — the caller's raw overrides (+ catalogue on GET). */
export interface PreferencesResponse {
  values: Record<string, unknown>;
  registry?: Record<string, PreferenceCatalogueEntry>;
}
