/**
 * SLA due-date simulation — a forward-walk over a calendar's business hours (Phase F2.7 hardening).
 *
 * ⚠️ ISOLATED CONFIG AID. No backend SLA-simulation endpoint exists (`apps/sla/urls.py` exposes
 * only policies / business-hours / dashboard), so this is a minimal client-side estimator used ONLY
 * for calendar validation + planning in the builder. The authoritative engine is the backend
 * `apps/sla/calculator.py` — this module is never on a production SLA execution path.
 *
 * LIMITATION: it interprets the start wall-clock as the calendar's local time and does not apply
 * timezone offsets or DST. Pure + framework-free.
 */
import type { Holiday, Interval } from "./api";
import { hhmmToMinutes, validateCalendar } from "./calendar-validation";

const JS_DAY_TO_KEY = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

function ymd(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function minutesToHHMM(total: number): string {
  const h = Math.floor(total / 60) % 24;
  const m = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export type SimulationResult = { dueISO: string; dueLabel: string } | { error: string };

/**
 * Walk `durationMinutes` of business time forward from `startISO`, consuming only the configured
 * working intervals and skipping holidays. Returns the estimated due wall-clock datetime.
 */
export function simulateDue(input: {
  weekly_hours: Record<string, Interval[]>;
  holidays: Holiday[];
  startISO: string;
  durationMinutes: number;
}): SimulationResult {
  const { weekly_hours, holidays, startISO, durationMinutes } = input;
  if (!startISO) return { error: "Pick a start date and time." };
  const start = new Date(startISO);
  if (Number.isNaN(start.getTime())) return { error: "Invalid start date/time." };
  if (!Number.isFinite(durationMinutes) || durationMinutes < 0) return { error: "Enter a non-negative duration." };

  // never simulate against a broken config (reuses the validation source of truth)
  if (validateCalendar({ name: "x", timezone: "x", weekly_hours, holidays }).hasErrors) {
    return { error: "Fix the calendar errors before simulating." };
  }

  const holidaySet = new Set(holidays.map((h) => (h.date ?? "").trim()).filter(Boolean));
  let remaining = durationMinutes;
  const cursor = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  let firstDay = true;
  const startMinutes = start.getHours() * 60 + start.getMinutes();

  // bound the walk so a fully-closed calendar can't loop forever
  for (let guard = 0; guard < 366 * 2; guard++) {
    const key = JS_DAY_TO_KEY[cursor.getDay()];
    const intervals = holidaySet.has(ymd(cursor))
      ? []
      : [...(weekly_hours[key] ?? [])]
          .map((iv) => ({ start: hhmmToMinutes(iv.start) ?? 0, end: hhmmToMinutes(iv.end) ?? 0 }))
          .sort((a, b) => a.start - b.start);

    for (const iv of intervals) {
      const from = firstDay ? Math.max(iv.start, startMinutes) : iv.start;
      if (from >= iv.end) continue;
      const avail = iv.end - from;
      if (remaining <= avail) {
        const dueMin = from + remaining;
        const due = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate(), Math.floor(dueMin / 60), dueMin % 60);
        return { dueISO: `${ymd(due)}T${minutesToHHMM(dueMin)}`, dueLabel: `${ymd(due)} ${minutesToHHMM(dueMin)}` };
      }
      remaining -= avail;
    }

    firstDay = false;
    cursor.setDate(cursor.getDate() + 1);
  }

  return { error: "SLA duration exceeds the simulation window (2 years) — check the calendar has working hours." };
}
