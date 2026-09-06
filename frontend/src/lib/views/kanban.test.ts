import { describe, expect, it } from "vitest";

import { applyMove, kanbanColumns, movePatch } from "./kanban";

const rows = [
  { id: "1", stage: "open" },
  { id: "2", stage: "won" },
  { id: "3", stage: "open" },
];

describe("kanbanColumns", () => {
  it("builds ordered status columns", () => {
    const cols = kanbanColumns(rows, "stage", ["open", "won", "lost"]);
    expect(cols.map((c) => c.key)).toEqual(["open", "won", "lost"]);
    expect(cols[0].records).toHaveLength(2);
  });
});

describe("movePatch", () => {
  it("is the field patch for the target column", () => {
    expect(movePatch("stage", "won")).toEqual({ stage: "won" });
  });
});

describe("applyMove (optimistic)", () => {
  it("returns a new array with the moved card's field updated", () => {
    const next = applyMove(rows, "1", "stage", "won");
    expect(next).not.toBe(rows); // new array
    expect(next.find((r) => r.id === "1")!.stage).toBe("won");
    expect(rows.find((r) => r.id === "1")!.stage).toBe("open"); // original unchanged (rollback source)
  });
  it("is a no-op (same ref) for an unknown id", () => {
    expect(applyMove(rows, "999", "stage", "won")).toBe(rows);
  });
});
