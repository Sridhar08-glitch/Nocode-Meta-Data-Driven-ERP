/**
 * Pure, framework-free validation helpers for the Business Calendar builder (Phase F2.7
 * hardening). Reusable by create/edit/import flows. No React dependencies.
 */
import type { Holiday, Interval } from "./api";
import { WEEKDAYS } from "./api";

const DAY_NAMES: Record<string, string> = {
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
  sun: "Sunday",
};

/** "HH:MM" → minutes since midnight, or null if not a valid 24h time. */
export function hhmmToMinutes(s: string): number | null {
  const m = /^(\d{2}):(\d{2})$/.exec((s ?? "").trim());
  if (!m) return null;
  const h = Number(m[1]);
  const min = Number(m[2]);
  if (h > 23 || min > 59) return null;
  return h * 60 + min;
}

function minutesToHHMM(total: number): string {
  const h = Math.floor(total / 60) % 24;
  const m = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

/** Human label for a day key (e.g. "mon" → "Monday"). */
export function dayName(day: string): string {
  return DAY_NAMES[day] ?? day;
}

/** Validate a single interval: both ends parse and start is strictly before end. Returns null if ok. */
export function validateInterval(iv: Interval): string | null {
  const start = hhmmToMinutes(iv.start);
  const end = hhmmToMinutes(iv.end);
  if (start === null || end === null) return "Enter valid start and end times.";
  if (start >= end) return `Start (${iv.start}) must be before end (${iv.end}).`;
  return null;
}

/** Validate a day's intervals: each well-formed + no overlaps (touching ends allowed). */
export function validateDayIntervals(intervals: Interval[]): string[] {
  const errs: string[] = [];
  const parsed: { start: number; end: number }[] = [];

  intervals.forEach((iv, i) => {
    const err = validateInterval(iv);
    if (err) {
      errs.push(`Shift ${i + 1}: ${err}`);
      return;
    }
    parsed.push({ start: hhmmToMinutes(iv.start)!, end: hhmmToMinutes(iv.end)! });
  });

  const sorted = [...parsed].sort((a, b) => a.start - b.start);
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i].start < sorted[i - 1].end) {
      errs.push(
        `Overlapping shifts (${minutesToHHMM(sorted[i - 1].start)}–${minutesToHHMM(sorted[i - 1].end)} and ${minutesToHHMM(sorted[i].start)}–${minutesToHHMM(sorted[i].end)}).`,
      );
      break;
    }
  }
  return errs;
}

/** Validate holidays: dates must be unique. Empty rows are ignored. */
export function validateHolidays(holidays: Holiday[]): string[] {
  const errs: string[] = [];
  const seen = new Set<string>();
  for (const h of holidays) {
    const date = (h.date ?? "").trim();
    if (!date) continue;
    if (seen.has(date)) errs.push(`Duplicate holiday date: ${date}.`);
    seen.add(date);
  }
  return errs;
}

export interface CalendarValidation {
  /** name/timezone-level errors */
  general: string[];
  /** day-key → list of error messages */
  days: Record<string, string[]>;
  /** holiday-section error messages */
  holidays: string[];
  hasErrors: boolean;
}

/**
 * Validate a whole calendar: required name + timezone, every day's intervals, and unique holidays.
 */
export function validateCalendar(input: {
  name?: string;
  timezone?: string;
  weekly_hours: Record<string, Interval[]>;
  holidays: Holiday[];
}): CalendarValidation {
  const general: string[] = [];
  if (!(input.name ?? "").trim()) general.push("Name is required.");
  if (!(input.timezone ?? "").trim()) general.push("Timezone is required.");

  const days: Record<string, string[]> = {};
  for (const day of WEEKDAYS) {
    const errs = validateDayIntervals(input.weekly_hours[day] ?? []);
    if (errs.length) days[day] = errs;
  }

  const holidays = validateHolidays(input.holidays);

  const hasErrors = general.length > 0 || Object.keys(days).length > 0 || holidays.length > 0;
  return { general, days, holidays, hasErrors };
}
