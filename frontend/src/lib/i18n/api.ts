/**
 * Localization client (Phase F2.6) — workspace locale + flat translation map over
 * `/api/v1/localization/`. The translations response is `{locale, translations}` where
 * translations is a FLAT map of dotted keys (`"ui.button.save": "Save"`).
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface WorkspaceLocale {
  id: string;
  default_locale: string;
  default_timezone: string;
  default_currency: string;
  enabled_locales: string[];
  date_format: string;
  time_format: string;
  number_decimal_separator: string;
  number_thousands_separator: string;
  created_at: string;
  updated_at: string;
}
export type WorkspaceLocaleWrite = Partial<
  Pick<
    WorkspaceLocale,
    | "default_locale"
    | "default_timezone"
    | "default_currency"
    | "enabled_locales"
    | "date_format"
    | "time_format"
    | "number_decimal_separator"
    | "number_thousands_separator"
  >
>;
export interface TranslationsResponse {
  locale: string;
  translations: Record<string, string>;
}

/** RTL locales — there's no backend flag; derive direction from the language subtag. */
const RTL_LANGS = new Set(["ar", "he", "fa", "ur", "ps", "dv", "yi"]);
export function isRtlLocale(locale: string): boolean {
  return RTL_LANGS.has(locale.slice(0, 2).toLowerCase());
}

const L = "/api/v1/localization";

export const localizationApi = {
  getLocale: () => apiGet<WorkspaceLocale>(`${L}/locale/`),
  updateLocale: (data: WorkspaceLocaleWrite) => apiSend<WorkspaceLocale>(`${L}/locale/`, "PATCH", data),
  translations: (locale: string, namespace?: string) =>
    apiGet<TranslationsResponse>(`${L}/translations/?locale=${encodeURIComponent(locale)}${namespace ? `&namespace=${namespace}` : ""}`),
};
