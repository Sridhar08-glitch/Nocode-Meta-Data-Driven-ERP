/** Kanban (Phase F2.1) — status columns + optimistic card-move helpers. Pure. */
import { groupByField } from "./grouping";
import { type Group, type Row, rowId } from "./types";

/** Build columns from rows grouped by `groupField`, optionally ordered by select options. */
export function kanbanColumns(rows: Row[], groupField: string, order?: string[]): Group[] {
  return groupByField(rows, groupField, order);
}

/** The field patch for moving a card to `targetKey` (sent to the update mutation). */
export function movePatch(groupField: string, targetKey: string): Record<string, string> {
  return { [groupField]: targetKey };
}

/**
 * Optimistically apply a card move to a row list — returns a NEW array with the moved row's
 * group field set to `targetKey`. The component renders this immediately and rolls back to the
 * previous array if the mutation fails. No-op (same ref) when the id isn't found.
 */
export function applyMove(rows: Row[], id: string, groupField: string, targetKey: string): Row[] {
  let changed = false;
  const next = rows.map((r) => {
    if (rowId(r) === id) {
      changed = true;
      return { ...r, [groupField]: targetKey };
    }
    return r;
  });
  return changed ? next : rows;
}
