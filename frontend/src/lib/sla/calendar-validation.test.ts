import { describe, expect, it } from "vitest";

import type { Holiday, Interval } from "./api";
import {
  hhmmToMinutes,
  validateCalendar,
  validateDayIntervals,
  validateHolidays,
  validateInterval,
} from "./calendar-validation";

const week = (over: Partial<Record<string, Interval[]>> = {}): Record<string, Interval[]> => ({
  mon: [], tue: [], wed: [], thu: [], fri: [], sat: [], sun: [],
  ...over,
});
const businessWeek = () =>
  week({
    mon: [{ start: "09:00", end: "17:00" }],
    tue: [{ start: "09:00", end: "17:00" }],
    wed: [{ start: "09:00", end: "17:00" }],
    thu: [{ start: "09:00", end: "17:00" }],
    fri: [{ start: "09:00", end: "17:00" }],
  });

describe("hhmmToMinutes", () => {
  it("parses valid times and rejects junk", () => {
    expect(hhmmToMinutes("09:30")).toBe(570);
    expect(hhmmToMinutes("00:00")).toBe(0);
    expect(hhmmToMinutes("24:00")).toBeNull();
    expect(hhmmToMinutes("9:30")).toBeNull();
    expect(hhmmToMinutes("nope")).toBeNull();
  });
});

describe("validateInterval", () => {
  it("accepts start < end", () => {
    expect(validateInterval({ start: "09:00", end: "17:00" })).toBeNull();
  });
  it("rejects start >= end", () => {
    expect(validateInterval({ start: "17:00", end: "09:00" })).toMatch(/must be before end/);
    expect(validateInterval({ start: "09:00", end: "09:00" })).toMatch(/must be before end/);
  });
  it("rejects unparseable times", () => {
    expect(validateInterval({ start: "9am", end: "17:00" })).toMatch(/valid start and end/);
  });
});

describe("validateDayIntervals", () => {
  it("flags overlapping shifts", () => {
    const errs = validateDayIntervals([{ start: "09:00", end: "12:00" }, { start: "11:00", end: "15:00" }]);
    expect(errs.some((e) => /Overlapping/.test(e))).toBe(true);
  });
  it("allows touching split shifts", () => {
    expect(validateDayIntervals([{ start: "09:00", end: "12:00" }, { start: "12:00", end: "17:00" }])).toEqual([]);
  });
});

describe("validateHolidays", () => {
  it("flags duplicate dates and ignores empty rows", () => {
    const holidays: Holiday[] = [{ date: "2026-12-25" }, { date: "" }, { date: "2026-12-25" }];
    expect(validateHolidays(holidays)).toEqual(["Duplicate holiday date: 2026-12-25."]);
  });
});

describe("validateCalendar", () => {
  it("accepts a well-formed calendar", () => {
    expect(validateCalendar({ name: "EMEA", timezone: "Europe/Paris", weekly_hours: businessWeek(), holidays: [] }).hasErrors).toBe(false);
  });

  it("requires a name and timezone", () => {
    const v = validateCalendar({ name: "", timezone: "", weekly_hours: businessWeek(), holidays: [] });
    expect(v.general).toEqual(["Name is required.", "Timezone is required."]);
    expect(v.hasErrors).toBe(true);
  });

  it("surfaces per-day and holiday errors", () => {
    const v = validateCalendar({
      name: "X",
      timezone: "UTC",
      weekly_hours: week({ mon: [{ start: "17:00", end: "09:00" }] }),
      holidays: [{ date: "2026-01-01" }, { date: "2026-01-01" }],
    });
    expect(v.days.mon[0]).toMatch(/must be before end/);
    expect(v.holidays[0]).toMatch(/Duplicate holiday date/);
    expect(v.hasErrors).toBe(true);
  });
});
