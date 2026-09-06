/** Timeline (Phase F2.1) — ordered chronological events from a date field. Pure. */
import { sortByDate } from "./sorting";
import { type CalendarEvent, type Row, rowId, type SortDir, toText } from "./types";

export interface TimelineEvent extends CalendarEvent {
  /** raw ISO/date string for display. */
  at: string;
}

export function timelineEvents(
  rows: Row[],
  dateField: string,
  titleField?: string,
  dir: SortDir = "asc",
): TimelineEvent[] {
  return sortByDate(rows, dateField, dir)
    .filter((r) => !Number.isNaN(Date.parse(toText(r[dateField]))))
    .map((row) => {
      const at = toText(row[dateField]);
      return {
        id: rowId(row),
        day: at.slice(0, 10),
        at,
        title: toText(titleField ? row[titleField] : row.id) || "(untitled)",
        row,
      };
    });
}
