/**
 * NQL wire AST (Phase F1.9) — the canonical query shape the backend `/api/v1/nql/query/`
 * endpoint accepts (and that `recordsApi.list` filters compile down to). The builder edits
 * this exact shape so build → serialize → parse round-trips with no lossy intermediate form.
 *
 * Backend contract (apps/nql/ast.py): a query has an `entity`, optional `select`, a recursive
 * `filter` (AND/OR groups + comparison leaves), `sort`, `groupBy`, `aggregations`, `pagination`,
 * and an (accepted-but-not-executed-in-v1) `asOf`.
 */

/** Comparison operators usable on a leaf condition. */
export type ComparisonOp =
  | "="
  | "!="
  | ">"
  | ">="
  | "<"
  | "<="
  | "in"
  | "not in"
  | "contains"
  | "is null"
  | "is not null";

/** Boolean group combinators. */
export type GroupOp = "and" | "or";

/** Aggregation functions. */
export type AggFunc = "count" | "sum" | "avg" | "min" | "max";

/** Sort direction. */
export type SortDirection = "asc" | "desc";

/** A leaf comparison. `value` is omitted for the nullary operators. */
export interface Condition {
  field: string;
  op: ComparisonOp;
  value?: unknown;
}

/** A nested boolean group. */
export interface FilterGroup {
  op: GroupOp;
  conditions: FilterNode[];
}

/** Either a group or a leaf. */
export type FilterNode = FilterGroup | Condition;

export interface SortClause {
  field: string;
  direction: SortDirection;
}

export interface Aggregation {
  func: AggFunc;
  field?: string;
  alias?: string;
}

export interface Pagination {
  limit?: number;
  offset?: number;
  page?: number;
}

/** The full query AST — this is exactly what the wire endpoint accepts. */
export interface NqlQuery {
  entity: string;
  select?: string[];
  filter?: FilterNode;
  sort?: SortClause[];
  groupBy?: string[];
  aggregations?: Aggregation[];
  pagination?: Pagination;
  asOf?: string;
}

// ── operator metadata (drives the builder UI) ──────────────────────────────────────

/** Operators that take no value (`field IS NULL`). */
export const NULLARY_OPS: readonly ComparisonOp[] = ["is null", "is not null"];

/** Operators whose value must be a list. */
export const LIST_OPS: readonly ComparisonOp[] = ["in", "not in"];

export function isNullaryOp(op: ComparisonOp): boolean {
  return NULLARY_OPS.includes(op);
}

export function isListOp(op: ComparisonOp): boolean {
  return LIST_OPS.includes(op);
}

/** A group node is one with a `conditions` array. */
export function isGroup(node: FilterNode): node is FilterGroup {
  return (node as FilterGroup).conditions !== undefined;
}

/** Operator picker options (value + human label). */
export const COMPARISON_OPTIONS: { value: ComparisonOp; label: string }[] = [
  { value: "=", label: "equals" },
  { value: "!=", label: "not equals" },
  { value: ">", label: "greater than" },
  { value: ">=", label: "greater or equal" },
  { value: "<", label: "less than" },
  { value: "<=", label: "less or equal" },
  { value: "in", label: "in" },
  { value: "not in", label: "not in" },
  { value: "contains", label: "contains" },
  { value: "is null", label: "is empty" },
  { value: "is not null", label: "is not empty" },
];

export const AGG_FUNC_OPTIONS: { value: AggFunc; label: string }[] = [
  { value: "count", label: "Count" },
  { value: "sum", label: "Sum" },
  { value: "avg", label: "Average" },
  { value: "min", label: "Minimum" },
  { value: "max", label: "Maximum" },
];

export const GROUP_OP_OPTIONS: { value: GroupOp; label: string }[] = [
  { value: "and", label: "All (AND)" },
  { value: "or", label: "Any (OR)" },
];

/** Server-resolved magic values usable as a condition value. */
export const MAGIC_VALUES: { value: string; label: string }[] = [
  { value: "@me", label: "Current user" },
  { value: "@today", label: "Today" },
  { value: "@yesterday", label: "Yesterday" },
  { value: "@last_week", label: "Last week" },
  { value: "@this_month", label: "This month" },
  { value: "@now", label: "Now" },
];

/** Result of executing a query against `/api/v1/nql/query/`. */
export interface NqlResult {
  rows: Record<string, unknown>[];
  count: number;
}
