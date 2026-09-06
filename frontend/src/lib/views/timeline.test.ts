import { describe, expect, it } from "vitest";

import { timelineEvents } from "./timeline";

describe("timelineEvents", () => {
  const rows = [
    { id: "a", at: "2026-03-01", name: "Launch" },
    { id: "b", at: "2026-01-01", name: "Kickoff" },
    { id: "c", at: "bad", name: "Dropme" },
  ];

  it("returns chronological events (desc) and drops undated rows", () => {
    const events = timelineEvents(rows, "at", "name", "desc");
    expect(events.map((e) => e.id)).toEqual(["a", "b"]);
    expect(events[0]).toMatchObject({ id: "a", at: "2026-03-01", day: "2026-03-01", title: "Launch" });
  });

  it("orders ascending when asked", () => {
    expect(timelineEvents(rows, "at", "name", "asc").map((e) => e.id)).toEqual(["b", "a"]);
  });

  it("falls back to the id for the title", () => {
    expect(timelineEvents([{ id: "x", at: "2026-01-01" }], "at")[0].title).toBe("x");
  });
});
