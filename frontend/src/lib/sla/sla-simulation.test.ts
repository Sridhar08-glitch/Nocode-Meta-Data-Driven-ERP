import { describe, expect, it } from "vitest";

import type { Interval } from "./api";
import { simulateDue } from "./sla-simulation";

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

describe("simulateDue", () => {
  it("resolves a same-day due time", () => {
    expect(simulateDue({ weekly_hours: businessWeek(), holidays: [], startISO: "2026-06-29T09:00", durationMinutes: 120 })).toEqual({
      dueISO: "2026-06-29T11:00",
      dueLabel: "2026-06-29 11:00",
    });
  });

  it("rolls over the weekend (Fri 16:30 + 60m → Mon 09:30)", () => {
    expect(simulateDue({ weekly_hours: businessWeek(), holidays: [], startISO: "2026-06-26T16:30", durationMinutes: 60 })).toEqual({
      dueISO: "2026-06-29T09:30",
      dueLabel: "2026-06-29 09:30",
    });
  });

  it("skips a holiday", () => {
    expect(
      simulateDue({ weekly_hours: businessWeek(), holidays: [{ date: "2026-06-29" }], startISO: "2026-06-26T16:30", durationMinutes: 60 }),
    ).toEqual({ dueISO: "2026-06-30T09:30", dueLabel: "2026-06-30 09:30" });
  });

  it("consumes split shifts across a single day", () => {
    const split = week({ mon: [{ start: "09:00", end: "12:00" }, { start: "13:00", end: "17:00" }] });
    // 09:00 + 240 business min = 3h in morning (→12:00) then 1h after lunch → 14:00
    expect(simulateDue({ weekly_hours: split, holidays: [], startISO: "2026-06-29T09:00", durationMinutes: 240 })).toEqual({
      dueISO: "2026-06-29T14:00",
      dueLabel: "2026-06-29 14:00",
    });
  });

  it("errors on a fully-closed calendar", () => {
    expect(simulateDue({ weekly_hours: week(), holidays: [], startISO: "2026-06-29T09:00", durationMinutes: 60 })).toHaveProperty("error");
  });

  it("refuses to simulate against an invalid calendar", () => {
    expect(
      simulateDue({ weekly_hours: week({ mon: [{ start: "17:00", end: "09:00" }] }), holidays: [], startISO: "2026-06-29T09:00", durationMinutes: 60 }),
    ).toEqual({ error: expect.stringMatching(/Fix the calendar errors/) });
  });

  it("validates inputs", () => {
    expect(simulateDue({ weekly_hours: businessWeek(), holidays: [], startISO: "", durationMinutes: 60 })).toHaveProperty("error");
    expect(simulateDue({ weekly_hours: businessWeek(), holidays: [], startISO: "2026-06-29T09:00", durationMinutes: -5 })).toHaveProperty("error");
  });
});
