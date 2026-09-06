import { describe, expect, it } from "vitest";

import { calendarEvents, dayKey, groupByDay, monthMatrix, reschedulePatch } from "./calendar";

describe("dayKey", () => {
  it("extracts yyyy-mm-dd or null", () => {
    expect(dayKey("2026-03-15T10:00:00Z")).toBe("2026-03-15");
    expect(dayKey("2026-03-15")).toBe("2026-03-15");
    expect(dayKey("")).toBeNull();
    expect(dayKey("not-a-date")).toBeNull();
  });
});

describe("groupByDay", () => {
  it("buckets rows by day and drops undated rows", () => {
    const rows = [
      { id: "1", due: "2026-03-15" },
      { id: "2", due: "2026-03-15T09:00:00Z" },
      { id: "3", due: "" },
    ];
    const g = groupByDay(rows, "due");
    expect(g["2026-03-15"]).toHaveLength(2);
    expect(Object.keys(g)).toEqual(["2026-03-15"]);
  });
});

describe("calendarEvents", () => {
  it("builds events with title fallback, dropping undated rows", () => {
    const rows = [
      { id: "1", due: "2026-03-15", name: "Call" },
      { id: "2", due: "bad", name: "Skip" },
    ];
    const events = calendarEvents(rows, "due", "name");
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ id: "1", day: "2026-03-15", title: "Call" });
    expect(calendarEvents([{ id: "9", due: "2026-01-01" }], "due")[0].title).toBe("9");
  });
});

describe("monthMatrix", () => {
  it("returns a 6×7 grid flagging in-month days", () => {
    const weeks = monthMatrix(2026, 2); // March 2026
    expect(weeks).toHaveLength(6);
    expect(weeks.every((w) => w.length === 7)).toBe(true);
    // 2026-03-01 is a Sunday → first cell is in-month
    expect(weeks[0][0]).toEqual({ day: "2026-03-01", inMonth: true });
    expect(weeks.flat().some((c) => !c.inMonth)).toBe(true); // trailing days of next month
  });
});

describe("reschedulePatch", () => {
  it("produces the date-field patch", () => {
    expect(reschedulePatch("due", "2026-04-01")).toEqual({ due: "2026-04-01" });
  });
});
