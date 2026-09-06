import { describe, expect, it } from "vitest";

import { sortByDate, sortByField } from "./sorting";

describe("sortByDate", () => {
  const rows = [
    { id: "a", d: "2026-03-01" },
    { id: "b", d: "2026-01-01" },
    { id: "c", d: "2026-02-01" },
  ];
  it("sorts ascending and descending", () => {
    expect(sortByDate(rows, "d").map((r) => r.id)).toEqual(["b", "c", "a"]);
    expect(sortByDate(rows, "d", "desc").map((r) => r.id)).toEqual(["a", "c", "b"]);
  });
  it("sinks unparseable dates to the end and is stable among them", () => {
    const withBad = [{ id: "x", d: "" }, { id: "y", d: "nope" }, { id: "z", d: "2026-01-01" }];
    expect(sortByDate(withBad, "d").map((r) => r.id)).toEqual(["z", "x", "y"]);
  });
});

describe("sortByField", () => {
  it("sorts numerically when values are numbers", () => {
    const rows = [{ id: "a", n: 10 }, { id: "b", n: 2 }, { id: "c", n: 30 }];
    expect(sortByField(rows, "n").map((r) => r.id)).toEqual(["b", "a", "c"]);
    expect(sortByField(rows, "n", "desc").map((r) => r.id)).toEqual(["c", "a", "b"]);
  });
  it("sorts as strings otherwise, stably", () => {
    const rows = [{ id: "a", s: "Banana" }, { id: "b", s: "apple" }, { id: "c", s: "apple" }];
    expect(sortByField(rows, "s").map((r) => r.id)).toEqual(["b", "c", "a"]);
  });
});
