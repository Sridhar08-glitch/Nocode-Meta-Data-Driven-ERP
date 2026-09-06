/**
 * NQL builder (Phase F1.9) — pure, immutable helpers that construct and edit an {@link NqlQuery}
 * and serialize it to the clean wire shape the backend accepts. The builder operates directly on
 * the wire AST (no separate internal form), so `serialize` is idempotent and build→serialize
 * round-trips losslessly. Filter-tree edits address nodes by a numeric `path` (indices descending
 * through `conditions`), the same explicit-operation style used by the Form Builder.
 */
import {
  type Aggregation,
  type Condition,
  type FilterGroup,
  type FilterNode,
  type GroupOp,
  type NqlQuery,
  type Pagination,
  isGroup,
  isListOp,
  isNullaryOp,
} from "./types";

// ── constructors ───────────────────────────────────────────────────────────────────
export function emptyCondition(field = ""): Condition {
  return { field, op: "=", value: "" };
}

export function emptyGroup(op: GroupOp = "and"): FilterGroup {
  return { op, conditions: [] };
}

export function emptyQuery(entity: string): NqlQuery {
  return {
    entity,
    select: [],
    filter: emptyGroup("and"),
    sort: [],
    groupBy: [],
    aggregations: [],
  };
}

// ── filter-tree navigation + immutable edits ─────────────────────────────────────────
/** Resolve the node at `path`, or `undefined` if the path escapes the tree. */
export function getNodeAt(root: FilterNode, path: number[]): FilterNode | undefined {
  let node: FilterNode | undefined = root;
  for (const idx of path) {
    if (!node || !isGroup(node)) return undefined;
    node = node.conditions[idx];
  }
  return node;
}

/** Rebuild the tree, applying `fn` to the node at `path`. Out-of-tree paths are no-ops. */
function mapNodeAt(root: FilterNode, path: number[], fn: (n: FilterNode) => FilterNode): FilterNode {
  if (path.length === 0) return fn(root);
  if (!isGroup(root)) return root;
  const [head, ...rest] = path;
  if (head < 0 || head >= root.conditions.length) return root;
  const conditions = root.conditions.map((c, i) => (i === head ? mapNodeAt(c, rest, fn) : c));
  return { ...root, conditions };
}

/** Append a child node to the group at `path`. */
export function addToGroup(root: FilterNode, path: number[], node: FilterNode): FilterNode {
  return mapNodeAt(root, path, (g) =>
    isGroup(g) ? { ...g, conditions: [...g.conditions, node] } : g,
  );
}

/** Remove the node at `path`. The root cannot be removed (returns the tree unchanged). */
export function removeAt(root: FilterNode, path: number[]): FilterNode {
  if (path.length === 0) return root;
  const parent = path.slice(0, -1);
  const idx = path[path.length - 1];
  return mapNodeAt(root, parent, (g) =>
    isGroup(g) ? { ...g, conditions: g.conditions.filter((_, i) => i !== idx) } : g,
  );
}

/** Switch a group node between AND/OR. */
export function setGroupOp(root: FilterNode, path: number[], op: GroupOp): FilterNode {
  return mapNodeAt(root, path, (n) => (isGroup(n) ? { ...n, op } : n));
}

/** Patch a leaf condition, re-normalising the value for the (possibly new) operator. */
export function updateCondition(
  root: FilterNode,
  path: number[],
  patch: Partial<Condition>,
): FilterNode {
  return mapNodeAt(root, path, (n) =>
    isGroup(n) ? n : normalizeCondition({ ...n, ...patch }),
  );
}

/** Coerce a condition's value to match its operator (drop for nullary, array for list ops). */
export function normalizeCondition(c: Condition): Condition {
  if (isNullaryOp(c.op)) {
    return { field: c.field, op: c.op }; // nullary ops carry no value
  }
  if (isListOp(c.op)) {
    const value = Array.isArray(c.value)
      ? c.value
      : c.value === undefined || c.value === null || c.value === ""
        ? []
        : [c.value];
    return { ...c, value };
  }
  return c;
}

// ── serialization (builder AST → clean wire AST) ────────────────────────────────────
function serializeFilter(node: FilterNode): FilterNode | undefined {
  if (isGroup(node)) {
    const conditions = node.conditions
      .map(serializeFilter)
      .filter((n): n is FilterNode => n !== undefined);
    if (conditions.length === 0) return undefined;
    return { op: node.op, conditions };
  }
  if (!node.field) return undefined; // incomplete leaf is dropped
  return normalizeCondition(node);
}

function serializeAgg(a: Aggregation): Aggregation {
  const out: Aggregation = { func: a.func };
  if (a.field) out.field = a.field;
  if (a.alias) out.alias = a.alias;
  return out;
}

function serializePagination(p: Pagination): Pagination | undefined {
  const out: Pagination = {};
  if (typeof p.limit === "number") out.limit = p.limit;
  if (typeof p.offset === "number") out.offset = p.offset;
  if (typeof p.page === "number") out.page = p.page;
  return Object.keys(out).length ? out : undefined;
}

/** Produce the minimal wire AST: empty clauses omitted, incomplete filter nodes pruned. */
export function serialize(q: NqlQuery): NqlQuery {
  const out: NqlQuery = { entity: q.entity };
  if (q.select && q.select.length) out.select = [...q.select];
  if (q.filter) {
    const filter = serializeFilter(q.filter);
    if (filter) out.filter = filter;
  }
  if (q.sort && q.sort.length) {
    out.sort = q.sort.map((s) => ({ field: s.field, direction: s.direction }));
  }
  if (q.groupBy && q.groupBy.length) out.groupBy = [...q.groupBy];
  if (q.aggregations && q.aggregations.length) out.aggregations = q.aggregations.map(serializeAgg);
  if (q.pagination) {
    const pagination = serializePagination(q.pagination);
    if (pagination) out.pagination = pagination;
  }
  if (q.asOf) out.asOf = q.asOf;
  return out;
}

// ── validation ──────────────────────────────────────────────────────────────────────
/** Returns a list of human-readable problems; empty = valid enough to run. */
export function validate(q: NqlQuery): string[] {
  const errors: string[] = [];
  if (!q.entity) errors.push("An entity is required.");
  if (q.filter) collectFilterErrors(q.filter, errors);
  for (const agg of q.aggregations ?? []) {
    if (agg.func !== "count" && !agg.field) {
      errors.push(`Aggregation "${agg.func}" needs a field.`);
    }
  }
  return errors;
}

function collectFilterErrors(node: FilterNode, errors: string[]): void {
  if (isGroup(node)) {
    for (const child of node.conditions) collectFilterErrors(child, errors);
    return;
  }
  if (!node.field) {
    errors.push("A filter condition is missing its field.");
    return;
  }
  if (isListOp(node.op) && (!Array.isArray(node.value) || node.value.length === 0)) {
    errors.push(`"${node.field} ${node.op}" needs at least one value.`);
  }
}

// ── human-readable rendering ("view as NQL") ─────────────────────────────────────────
function valueText(value: unknown): string {
  if (Array.isArray(value)) return `(${value.map(valueText).join(", ")})`;
  if (typeof value === "string") return value.startsWith("@") ? value : `'${value}'`;
  if (value === null || value === undefined) return "''";
  return String(value);
}

function describeNode(node: FilterNode): string {
  if (isGroup(node)) {
    if (node.conditions.length === 0) return "";
    const joiner = node.op === "and" ? " AND " : " OR ";
    const parts = node.conditions.map(describeNode).filter(Boolean);
    if (parts.length === 0) return "";
    if (parts.length === 1) return parts[0];
    return `(${parts.join(joiner)})`;
  }
  if (!node.field) return "";
  if (isNullaryOp(node.op)) return `${node.field} ${node.op}`;
  return `${node.field} ${node.op} ${valueText(node.value)}`;
}

/** Render the query as a readable NQL-ish string for the "view as NQL" panel. */
export function describe(q: NqlQuery): string {
  const cols = q.select && q.select.length ? q.select.join(", ") : "*";
  const aggs = (q.aggregations ?? []).map((a) =>
    a.field ? `${a.func}(${a.field})` : `${a.func}(*)`,
  );
  // `cols` is "*" only when there are no explicit columns; suppress it when aggregations stand in.
  const projection = [cols === "*" && aggs.length ? "" : cols, ...aggs].filter(Boolean).join(", ");
  let out = `SELECT ${projection} FROM ${q.entity || "?"}`;
  const where = q.filter ? describeNode(q.filter) : "";
  if (where) out += ` WHERE ${where}`;
  if (q.groupBy && q.groupBy.length) out += ` GROUP BY ${q.groupBy.join(", ")}`;
  if (q.sort && q.sort.length) {
    out += ` ORDER BY ${q.sort.map((s) => `${s.field} ${s.direction.toUpperCase()}`).join(", ")}`;
  }
  if (q.pagination?.limit !== undefined) out += ` LIMIT ${q.pagination.limit}`;
  if (q.pagination?.offset !== undefined) out += ` OFFSET ${q.pagination.offset}`;
  return out;
}
