/**
 * Pure, framework-free validation for the Branding settings form (Phase F3.1 polish). Mirrors the
 * server's expectations (hex colors, sanitized CSS) so admins get inline feedback before save.
 */
import type { BrandingSettings } from "./api";

const HEX = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

/** A value is a valid CSS hex color (`#rgb` or `#rrggbb`). Empty is treated as "unset" (valid). */
export function isHexColor(value: string): boolean {
  return HEX.test(value.trim());
}

const MAX_CSS_BYTES = 20_000;

/** Validate custom CSS for obvious authoring mistakes. Returns an error string, or null if ok. */
export function validateCustomCss(css: string): string | null {
  const text = css ?? "";
  if (text.length > MAX_CSS_BYTES) return `Custom CSS is too large (${text.length} chars; max ${MAX_CSS_BYTES}).`;

  let depth = 0;
  for (const ch of text) {
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth < 0) return "Unbalanced braces: a “}” has no matching “{”.";
    }
  }
  if (depth !== 0) return "Unbalanced braces: a “{” is never closed.";

  if (/\{\s*\}/.test(text)) return "Empty rule: a selector has an empty “{ }” block.";
  return null;
}

const COLOR_KEYS: (keyof BrandingSettings)[] = [
  "color_primary",
  "color_secondary",
  "color_accent",
  "color_background",
  "color_surface",
  "color_text_primary",
];

export interface BrandingValidation {
  /** color-field key → error message (only invalid, non-empty fields appear) */
  colors: Partial<Record<string, string>>;
  cssError: string | null;
  hasErrors: boolean;
}

/** Validate the editable branding form: non-empty colors must be hex; custom CSS must be well-formed. */
export function validateBrandingForm(form: BrandingSettings): BrandingValidation {
  const colors: Partial<Record<string, string>> = {};
  for (const key of COLOR_KEYS) {
    const v = (form[key] as string | undefined) ?? "";
    if (v.trim() && !isHexColor(v)) colors[key as string] = "Enter a hex color like #2563eb.";
  }
  const cssError = form.custom_css ? validateCustomCss(form.custom_css) : null;
  const hasErrors = Object.keys(colors).length > 0 || cssError !== null;
  return { colors, cssError, hasErrors };
}
