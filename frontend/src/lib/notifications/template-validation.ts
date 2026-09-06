/**
 * Notification-template variable validation (Phase F2.7 hardening). Pure + framework-free so the
 * builder and tests share one source of truth. The backend renderer (safe `string.Template`) stays
 * authoritative on delivery — this only guards obvious authoring mistakes before save.
 */

/**
 * Supported `${var}` keys offered by the notification render context. Unknown variables are
 * blocked at save so typos (e.g. `custmer_name`) are caught early. Extend this list as the
 * server render context grows — see `apps/notifications/renderer.py`.
 */
export const KNOWN_TEMPLATE_VARS = [
  "actor_name",
  "actor_email",
  "workspace_name",
  "record_title",
  "record_id",
  "entity_label",
  "entity_slug",
  "action_url",
  "recipient_name",
  "comment_body",
  "approval_status",
  "sla_metric",
  "due_at",
  "customer_name",
  "ticket_id",
] as const;

const known = new Set<string>(KNOWN_TEMPLATE_VARS);

/** Extract every well-formed `${name}` variable referenced across the given parts (deduped). */
export function extractVariables(...parts: string[]): string[] {
  const found = new Set<string>();
  for (const part of parts) {
    for (const m of Array.from((part ?? "").matchAll(/\$\{(\w+)\}/g))) found.add(m[1]);
  }
  return Array.from(found);
}

export interface TemplateValidation {
  /** raw malformed tokens, e.g. "${ }", "${na me}", or an unterminated "${name" */
  malformed: string[];
  /** well-formed but unrecognised variable names */
  unknown: string[];
  /** human-readable error messages (empty = valid) */
  errors: string[];
}

/**
 * Validate template parts (subject, body): detect malformed variables, unmatched braces / invalid
 * syntax, and unknown variable names. Touches the Python `string.Template` `${name}` form only.
 *
 * @param knownVars supported variable allowlist (defaults to {@link KNOWN_TEMPLATE_VARS}); pass an
 *   empty array to skip the unknown-variable check when no metadata is available.
 */
export function validateTemplate(parts: string[], knownVars: readonly string[] = KNOWN_TEMPLATE_VARS): TemplateValidation {
  const allow = knownVars === KNOWN_TEMPLATE_VARS ? known : new Set<string>(knownVars);
  const checkUnknown = knownVars.length > 0;
  const malformed = new Set<string>();
  const unknown = new Set<string>();

  for (const raw of parts) {
    const text = raw ?? "";
    // well-formed-looking ${...} (anything up to the next "}")
    for (const m of Array.from(text.matchAll(/\$\{([^}]*)\}/g))) {
      const inner = m[1];
      if (!/^\w+$/.test(inner)) malformed.add(m[0]);
      else if (checkUnknown && !allow.has(inner)) unknown.add(inner);
    }
    // unterminated "${" with no closing brace before end-of-line (unmatched opening brace)
    for (const m of Array.from(text.matchAll(/\$\{[^}\n]*$/gm))) malformed.add(m[0]);
  }

  const malformedList = Array.from(malformed);
  const unknownList = Array.from(unknown);
  const errors = [
    ...malformedList.map((t) => `Malformed variable: ${t}`),
    ...unknownList.map((v) => `Unknown variable: ${v}`),
  ];
  return { malformed: malformedList, unknown: unknownList, errors };
}
