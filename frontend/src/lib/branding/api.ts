/**
 * Branding admin client (Phase F3.1) — white-label settings + SMTP over `/api/v1/branding/`
 * (backend Phase 1.23). Admin-only writes. The SMTP password is write-only (`password` in, never
 * read back — only `password_ref`/`is_verified` come out). CSS is sanitized server-side.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export interface BrandingSettings {
  id?: string;
  app_name?: string;
  logo_url?: string;
  favicon_url?: string;
  color_primary?: string;
  color_secondary?: string;
  color_accent?: string;
  color_background?: string;
  color_surface?: string;
  color_text_primary?: string;
  color_text_muted?: string;
  font_family_heading?: string;
  font_family_body?: string;
  default_theme?: string;
  allow_theme_toggle?: boolean;
  ui_density?: string;
  border_radius?: string;
  custom_css?: string;
  login_headline?: string;
  login_subtext?: string;
  login_background_url?: string;
  email_from_name?: string;
}

export interface SMTPConfig {
  id?: string;
  host?: string;
  port?: number;
  username?: string;
  password_ref?: string;
  use_tls?: boolean;
  use_ssl?: boolean;
  from_email?: string;
  from_name?: string;
  is_verified?: boolean;
}
export interface SMTPWrite {
  host: string;
  port: number;
  username: string;
  password?: string;
  use_tls?: boolean;
  use_ssl?: boolean;
  from_email: string;
  from_name?: string;
}

const B = "/api/v1/branding";

export const brandingApi = {
  get: () => apiGet<BrandingSettings>(`${B}/`),
  update: (data: Partial<BrandingSettings>) => apiSend<BrandingSettings>(`${B}/`, "PATCH", data),
  getSmtp: () => apiGet<SMTPConfig | Record<string, never>>(`${B}/smtp/`),
  saveSmtp: (data: SMTPWrite) => apiSend<SMTPConfig>(`${B}/smtp/`, "PATCH", data),
  testSmtp: () => apiSend<{ success: boolean; error?: string }>(`${B}/smtp/test/`, "POST"),
};
