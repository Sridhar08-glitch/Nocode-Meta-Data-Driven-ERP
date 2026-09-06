/**
 * Conditional field visibility (Phase F1.6) — pure, so it's exhaustively testable.
 *
 * A rule watches `field`, compares with `op`/`value`, and applies `action` ("show" |
 * "hide") to its targets (`target_field` or `targets[]`):
 *   - hide: targets are hidden WHEN the condition is true.
 *   - show: targets are hidden UNLESS the condition is true (show-when).
 * Returns the set of hidden field slugs given the current form values.
 */
export interface ConditionalRule {
  field: string;
  op?: string;
  value?: unknown;
  action?: "show" | "hide";
  target_field?: string;
  targets?: string[];
}

function isEmpty(v: unknown): boolean {
  return v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);
}

function compare(actual: unknown, op: string, expected: unknown): boolean {
  switch (op) {
    case "=":
    case "==":
    case "eq":
      return String(actual) === String(expected);
    case "!=":
    case "ne":
      return String(actual) !== String(expected);
    case ">":
      return Number(actual) > Number(expected);
    case ">=":
      return Number(actual) >= Number(expected);
    case "<":
      return Number(actual) < Number(expected);
    case "<=":
      return Number(actual) <= Number(expected);
    case "empty":
    case "is_empty":
      return isEmpty(actual);
    case "not_empty":
    case "is_not_empty":
      return !isEmpty(actual);
    case "in":
      return Array.isArray(expected) && expected.map(String).includes(String(actual));
    case "contains":
      return Array.isArray(actual)
        ? actual.map(String).includes(String(expected))
        : String(actual).includes(String(expected));
    default:
      // unknown operator → truthy presence check (safe default)
      return !isEmpty(actual);
  }
}

function ruleTargets(rule: ConditionalRule): string[] {
  const list = [...(rule.targets ?? [])];
  if (rule.target_field) list.push(rule.target_field);
  return list;
}

export function evaluateHiddenFields(
  rules: ConditionalRule[] | undefined,
  values: Record<string, unknown>,
): Set<string> {
  const hidden = new Set<string>();
  for (const rule of rules ?? []) {
    if (!rule || !rule.field) continue;
    const met = compare(values[rule.field], rule.op ?? "not_empty", rule.value);
    const action = rule.action ?? "show";
    const targets = ruleTargets(rule);
    for (const t of targets) {
      if (action === "hide" && met) hidden.add(t);
      if (action === "show" && !met) hidden.add(t);
    }
  }
  return hidden;
}
