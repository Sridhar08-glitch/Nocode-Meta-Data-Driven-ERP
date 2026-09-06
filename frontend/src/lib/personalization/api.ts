import { apiGet, apiSend } from "@/lib/api/request";
import type { EffectiveAppearance } from "@/lib/branding/apply";

import type { AppearanceResponse, PreferencesResponse } from "./types";

/**
 * Personalization data layer (Phase P0) — /api/v1/me/. Per-user appearance preferences that
 * overlay the workspace branding through the SAME applyBranding pipeline. No second theme engine.
 */
export const personalizationApi = {
  appearance: () => apiGet<AppearanceResponse>("/api/v1/me/appearance/"),
  preferences: () => apiGet<PreferencesResponse>("/api/v1/me/preferences/"),
  savePreferences: (values: Partial<EffectiveAppearance>) =>
    apiSend<PreferencesResponse>("/api/v1/me/preferences/", "PUT", { values }),
  resetPreferences: (keys?: string[]) =>
    apiSend<PreferencesResponse>("/api/v1/me/preferences/reset/", "POST", keys ? { keys } : {}),
};
