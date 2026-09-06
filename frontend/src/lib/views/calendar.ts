/** Calendar (Phase F2.1) — date bucketing + event generation + reschedule patch. Pure. */
import { type CalendarEvent, type Row, rowId, toText } from "./types";

/** yyyy-mm-dd for a date-ish value, or null when unparseable/empty. */
export function dayKey(value: unknown): string | null {
  const s = toText(value);
  if (!s) return null;
  const t = Date.parse(s);
  if (Number.isNaN(t)) return null;
  return s.slice(0, 10);
}

export function groupByDay(rows: Row[], dateField: string): Record<string, Row[]> {
  const out: Record<string, Row[]> = {};
  for (const row of rows) {
    const k = dayKey(row[dateField]);
    if (!k) continue;
    (out[k] ??= []).push(row);
  }
  return out;
}

/** Generate calendar events from rows; rows without a valid date are dropped. */
export function calendarEvents(rows: Row[], dateField: string, titleField?: string): CalendarEvent[] {
  const events: CalendarEvent[] = [];
  for (const row of rows) {
    const day = dayKey(row[dateField]);
    if (!day) continue;
    events.push({
      id: rowId(row),
      day,
      title: toText(titleField ? row[titleField] : row.id) || "(untitled)",
      row,
    });
  }
  return events;
}

export interface CalendarCell {
  day: string; // yyyy-mm-dd
  inMonth: boolean;
}

/** A 6×7 month matrix (weeks starting Sunday) for `year`/`month` (month is 0-based). */
export function monthMatrix(year: number, month: number): CalendarCell[][] {
  const first = new Date(year, month, 1);
  const start = new Date(year, month, 1 - first.getDay()); // back up to Sunday
  const weeks: CalendarCell[][] = [];
  for (let w = 0; w < 6; w++) {
    const week: CalendarCell[] = [];
    for (let d = 0; d < 7; d++) {
      const cur = new Date(start.getFullYear(), start.getMonth(), start.getDate() + w * 7 + d);
      const iso = `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}-${String(cur.getDate()).padStart(2, "0")}`;
      week.push({ day: iso, inMonth: cur.getMonth() === month });
    }
    weeks.push(week);
  }
  return weeks;
}

/** The patch to reschedule a record to a new day (optimistic move writes this to the date field). */
export function reschedulePatch(dateField: string, newDay: string): Record<string, string> {
  return { [dateField]: newDay };
}
