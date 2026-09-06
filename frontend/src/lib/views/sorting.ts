/** Sorting (Phase F2.1) — stable sorts shared by timeline/gantt/table. Pure. */
import { type Row, type SortDir, toText } from "./types";

/** Sort rows by a date field; unparseable dates sink to the end (asc) regardless of dir. */
export function sortByDate(rows: Row[], dateField: string, dir: SortDir = "asc"): Row[] {
  const withTime = rows.map((r, i) => ({ r, i, t: Date.parse(toText(r[dateField])) }));
  withTime.sort((a, b) => {
    const aNan = Number.isNaN(a.t);
    const bNan = Number.isNaN(b.t);
    if (aNan && bNan) return a.i - b.i;
    if (aNan) return 1;
    if (bNan) return -1;
    return dir === "asc" ? a.t - b.t : b.t - a.t;
  });
  return withTime.map((x) => x.r);
}

/** Generic stable sort by a field (numeric when both parse as numbers, else string). */
export function sortByField(rows: Row[], field: string, dir: SortDir = "asc"): Row[] {
  const sign = dir === "asc" ? 1 : -1;
  return rows
    .map((r, i) => ({ r, i }))
    .sort((a, b) => {
      const av = a.r[field];
      const bv = b.r[field];
      const an = Number(av);
      const bn = Number(bv);
      let cmp: number;
      if (Number.isFinite(an) && Number.isFinite(bn)) cmp = an - bn;
      else cmp = toText(av).localeCompare(toText(bv));
      return cmp !== 0 ? cmp * sign : a.i - b.i;
    })
    .map((x) => x.r);
}
