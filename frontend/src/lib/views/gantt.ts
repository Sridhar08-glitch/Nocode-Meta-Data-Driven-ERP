/** Gantt (Phase F2.1) — start/end bars, progress, and dependency edges. Pure. */
import { type GanttConfig, type GanttItem, type Row, rowId, toText } from "./types";

export function ganttItems(rows: Row[], config: GanttConfig): GanttItem[] {
  const { startField, endField, progressField, dependencyField } = config;
  const parsed = rows
    .map((row) => ({ row, s: Date.parse(toText(row[startField])), e: Date.parse(toText(row[endField])) }))
    .filter((x) => !Number.isNaN(x.s) && !Number.isNaN(x.e) && x.e >= x.s);
  if (parsed.length === 0) return [];

  const min = Math.min(...parsed.map((p) => p.s));
  const max = Math.max(...parsed.map((p) => p.e));
  const span = max - min || 1;

  return parsed.map(({ row, s, e }) => {
    const rawProgress = progressField ? Number(row[progressField]) : NaN;
    const progress = Number.isFinite(rawProgress) ? Math.min(Math.max(rawProgress, 0), 100) / 100 : 0;
    const deps = dependencyField ? row[dependencyField] : undefined;
    const dependsOn = Array.isArray(deps)
      ? deps.map(toText).filter(Boolean)
      : deps
        ? [toText(deps)].filter(Boolean)
        : [];
    return {
      id: rowId(row),
      row,
      start: s,
      end: e,
      left: ((s - min) / span) * 100,
      width: Math.max(((e - s) / span) * 100, 1),
      progress,
      dependsOn,
    };
  });
}

/** Dependency edges among the laid-out items (drops dangling refs to missing items). */
export function dependencyEdges(items: GanttItem[]): { from: string; to: string }[] {
  const ids = new Set(items.map((i) => i.id));
  const edges: { from: string; to: string }[] = [];
  for (const item of items) {
    for (const dep of item.dependsOn) {
      if (ids.has(dep)) edges.push({ from: dep, to: item.id });
    }
  }
  return edges;
}
