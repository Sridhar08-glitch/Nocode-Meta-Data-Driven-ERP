/** Grouping (Phase F2.1) — bucket rows by a field's value (Kanban columns, chart groups). Pure. */
import { type Group, type Row, toText } from "./types";

export const UNASSIGNED = "__unassigned__";

/**
 * Group rows by `fieldSlug`. With `order` (e.g. a select field's option values) columns follow
 * that order; otherwise first-seen order. Null/empty values fall into a trailing "Unassigned" group.
 */
export function groupByField(rows: Row[], fieldSlug: string, order?: string[]): Group[] {
  const byKey = new Map<string, Group>();
  const ensure = (key: string, label: string) => {
    let g = byKey.get(key);
    if (!g) {
      g = { key, label, records: [] };
      byKey.set(key, g);
    }
    return g;
  };
  if (order) for (const o of order) ensure(o, o);
  for (const row of rows) {
    const raw = row[fieldSlug];
    const empty = raw === null || raw === undefined || raw === "";
    const key = empty ? UNASSIGNED : toText(raw);
    ensure(key, empty ? "Unassigned" : key).records.push(row);
  }
  return Array.from(byKey.values()).sort((a, b) =>
    a.key === UNASSIGNED ? 1 : b.key === UNASSIGNED ? -1 : 0,
  );
}
