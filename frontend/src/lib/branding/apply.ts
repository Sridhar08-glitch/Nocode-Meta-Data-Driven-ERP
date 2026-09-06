/**
 * White-label theming (Phase F1.4, completed in the Branding Platform enhancement).
 *
 * THE single runtime theme loader. Workspace branding stores hex colours / fonts / density / radius /
 * custom CSS / favicon; our Tailwind tokens are HSL channels (`--primary: "243 75% 59%"`). This module
 * converts + writes the CSS vars (and side-effects: favicon, custom-CSS `<style>`, density attribute)
 * on the document, re-theming the whole app live on workspace switch. `resetBranding` restores defaults.
 * It also snapshots the branding to localStorage so the pre-auth login page can render brand identity.
 *
 * There is exactly ONE branding source (WorkspaceBranding → this loader → CSS vars → Tailwind → every
 * component). No component themes itself; no second engine exists.
 */
export interface WorkspaceBranding {
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
  custom_css?: string;
  login_headline?: string;
  login_subtext?: string;
  login_background_url?: string;
  ui_density?: string;
  border_radius?: string;
}

/**
 * A user's resolved effective appearance (from GET /api/v1/me/appearance/). It OVERLAYS the
 * workspace branding on the SAME pipeline — no second theme engine. Theme is applied via
 * next-themes; everything else writes the same CSS vars / attributes applyBranding uses.
 */
export interface EffectiveAppearance {
  theme?: string; // light | dark | system  (driven through next-themes)
  accent?: string; // hex — overrides the branding accent
  density?: string; // comfortable | compact
  radius?: string; // none | sm | md | lg | xl
  font_scale?: number; // percent, 80–150 (accessibility)
  high_contrast?: boolean; // accessibility
  reduced_motion?: string; // system | on | off (accessibility)
}

const VAR_MAP: Record<string, string> = {
  color_primary: "--primary",
  color_secondary: "--secondary",
  color_accent: "--accent",
  color_background: "--background",
  color_surface: "--card",
  color_text_primary: "--foreground",
  color_text_muted: "--muted-foreground",
};

// Border-radius presets → the `--radius` base (Tailwind derives sm/md/lg from it).
const RADIUS_PRESETS: Record<string, string> = {
  none: "0px",
  sm: "0.25rem",
  md: "0.5rem",
  lg: "0.75rem",
  xl: "1rem",
};

const CUSTOM_CSS_ID = "nexus-workspace-css";
const SNAPSHOT_KEY = "nexus.branding";
const FONT_VARS = ["--font-heading", "--font-body"];

/** "#6366f1" → "243 75% 59%" (Tailwind HSL-channel format). Returns null if unparseable. */
export function hexToHslChannels(hex: string): string | null {
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  let h = m[1];
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  const r = parseInt(h.slice(0, 2), 16) / 255;
  const g = parseInt(h.slice(2, 4), 16) / 255;
  const b = parseInt(h.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  let hue = 0;
  let sat = 0;
  if (max !== min) {
    const d = max - min;
    sat = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) hue = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) hue = (b - r) / d + 2;
    else hue = (r - g) / d + 4;
    hue /= 6;
  }
  return `${Math.round(hue * 360)} ${Math.round(sat * 100)}% ${Math.round(l * 100)}%`;
}

/** Resolve the base `--radius` value for a preset key (or a raw rem/px value passthrough). */
export function radiusValue(preset: string | undefined): string | null {
  if (!preset) return null;
  return RADIUS_PRESETS[preset] ?? (/^\d/.test(preset) ? preset : null);
}

function setFavicon(url: string): void {
  if (typeof document === "undefined" || !url) return;
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    document.head.appendChild(link);
  }
  link.dataset.workspace = "1";
  link.href = url;
}

/** Inject workspace custom CSS. The value is sanitized SERVER-SIDE at save time (BrandingService
 * .sanitize_css); this only mounts the already-sanitized value into a single dedicated <style>. */
function injectCustomCss(css: string): void {
  if (typeof document === "undefined") return;
  let style = document.getElementById(CUSTOM_CSS_ID) as HTMLStyleElement | null;
  if (!css) {
    style?.remove();
    return;
  }
  if (!style) {
    style = document.createElement("style");
    style.id = CUSTOM_CSS_ID;
    document.head.appendChild(style);
  }
  style.textContent = css;
}

function snapshot(branding: WorkspaceBranding): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      SNAPSHOT_KEY,
      JSON.stringify({
        app_name: branding.app_name ?? "",
        logo_url: branding.logo_url ?? "",
        favicon_url: branding.favicon_url ?? "",
        login_headline: branding.login_headline ?? "",
        login_subtext: branding.login_subtext ?? "",
        login_background_url: branding.login_background_url ?? "",
      }),
    );
  } catch {
    /* storage may be unavailable — non-fatal */
  }
}

/** Read the last-known branding snapshot (used by the pre-auth login page). */
export function readBrandingSnapshot(): WorkspaceBranding | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SNAPSHOT_KEY);
    return raw ? (JSON.parse(raw) as WorkspaceBranding) : null;
  } catch {
    return null;
  }
}

export function applyBranding(branding: WorkspaceBranding | null | undefined): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (!branding) {
    resetBranding();
    return;
  }
  // 1. Colours → HSL-channel CSS vars.
  for (const [key, cssVar] of Object.entries(VAR_MAP)) {
    const hex = branding[key as keyof WorkspaceBranding];
    if (typeof hex === "string" && hex) {
      const hsl = hexToHslChannels(hex);
      if (hsl) root.style.setProperty(cssVar, hsl);
    }
  }
  // 2. Typography → font CSS vars (consumed by globals.css + Tailwind fontFamily tokens).
  if (branding.font_family_heading) root.style.setProperty("--font-heading", branding.font_family_heading);
  if (branding.font_family_body) root.style.setProperty("--font-body", branding.font_family_body);
  // 3. Border-radius preset → --radius base.
  const radius = radiusValue(branding.border_radius);
  if (radius) root.style.setProperty("--radius", radius);
  // 4. Density → data attribute (globals.css scales spacing/type off it).
  if (branding.ui_density) root.dataset.density = branding.ui_density;
  else delete root.dataset.density;
  // 5. Favicon + custom CSS (document-level side effects).
  if (branding.favicon_url) setFavicon(branding.favicon_url);
  injectCustomCss(branding.custom_css ?? "");
  // 6. Snapshot for the pre-auth login page.
  snapshot(branding);
}

export function resetBranding(): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  for (const cssVar of Object.values(VAR_MAP)) root.style.removeProperty(cssVar);
  for (const v of FONT_VARS) root.style.removeProperty(v);
  root.style.removeProperty("--radius");
  delete root.dataset.density;
  document.getElementById(CUSTOM_CSS_ID)?.remove();
  // The favicon + localStorage snapshot are intentionally NOT reset: the login page (post-logout,
  // pre-auth) still shows the last workspace's brand identity until a new workspace is loaded.
}

/**
 * Overlay a user's effective appearance ON TOP of applyBranding — reusing the same CSS vars and
 * data attributes. Call AFTER applyBranding on every change so user overrides win over workspace
 * defaults (except keys the workspace has locked, which the server already resolved out).
 * Theme (light/dark/system) is handled separately via next-themes, not here.
 */
export function applyPersonalization(appearance: EffectiveAppearance | null | undefined): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (!appearance) {
    resetPersonalization();
    return;
  }
  // Accent overrides the branding accent var.
  if (appearance.accent) {
    const hsl = hexToHslChannels(appearance.accent);
    if (hsl) root.style.setProperty("--accent", hsl);
  }
  // Density + radius reuse the exact branding mechanisms.
  if (appearance.density) root.dataset.density = appearance.density;
  const radius = radiusValue(appearance.radius);
  if (radius) root.style.setProperty("--radius", radius);
  // Font scaling (accessibility) — a multiplier consumed by the globals.css density rule.
  if (typeof appearance.font_scale === "number") {
    root.style.setProperty("--font-scale", String(appearance.font_scale / 100));
  } else {
    root.style.removeProperty("--font-scale");
  }
  // High contrast (accessibility) — toggles the `.hc` token modifier.
  root.classList.toggle("hc", appearance.high_contrast === true);
  // Reduced motion (accessibility): on → force reduce, off → force full, system → follow the OS.
  const rm = appearance.reduced_motion;
  if (rm === "on") root.dataset.motion = "reduce";
  else if (rm === "off") root.dataset.motion = "full";
  else delete root.dataset.motion;
}

/** Clear personalization overlays. Branding values reapply on the next applyBranding call. */
export function resetPersonalization(): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.style.removeProperty("--font-scale");
  root.classList.remove("hc");
  delete root.dataset.motion;
}
