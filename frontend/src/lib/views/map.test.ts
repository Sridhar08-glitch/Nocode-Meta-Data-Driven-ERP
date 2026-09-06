import { describe, expect, it } from "vitest";

import { extractMarkers } from "./map";

describe("extractMarkers", () => {
  it("projects lat/lng into a 0..100 box with north at top", () => {
    const rows = [
      { id: "n", lat: 50, lng: 0, name: "North" },
      { id: "s", lat: 10, lng: 20, name: "South" },
    ];
    const m = extractMarkers(rows, "lat", "lng", "name");
    expect(m).toHaveLength(2);
    const north = m.find((x) => x.id === "n")!;
    const south = m.find((x) => x.id === "s")!;
    expect(north.y).toBe(0); // max lat → top
    expect(south.y).toBe(100); // min lat → bottom
    expect(north.x).toBe(0); // min lng → left
    expect(south.x).toBe(100);
    expect(north.label).toBe("North");
  });

  it("drops rows with missing or out-of-range coordinates", () => {
    const rows = [
      { id: "ok", lat: 1, lng: 1 },
      { id: "nan", lat: "x", lng: 2 },
      { id: "oob", lat: 200, lng: 0 },
    ];
    expect(extractMarkers(rows, "lat", "lng").map((x) => x.id)).toEqual(["ok"]);
  });

  it("centers a single point (zero span → 0)", () => {
    const m = extractMarkers([{ id: "1", lat: 5, lng: 5 }], "lat", "lng");
    expect(m[0]).toMatchObject({ x: 0, y: 0 });
  });

  it("returns [] when there are no valid points", () => {
    expect(extractMarkers([{ id: "1", lat: null, lng: null }], "lat", "lng")).toEqual([]);
  });
});
