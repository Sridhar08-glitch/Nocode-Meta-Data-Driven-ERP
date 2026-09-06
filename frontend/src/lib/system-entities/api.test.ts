import { describe, expect, it } from "vitest";

import { recordsQuery } from "./api";

describe("recordsQuery (ListParams → B0 records query)", () => {
  it("translates limit/offset to page/page_size", () => {
    expect(recordsQuery({ limit: 25, offset: 0 })).toBe("?page=1&page_size=25");
    expect(recordsQuery({ limit: 25, offset: 50 })).toBe("?page=3&page_size=25");
  });
  it("maps sort direction", () => {
    expect(recordsQuery({ limit: 10, offset: 0, sort: [{ field: "principal", direction: "desc" }] })).toContain(
      "sort=-principal",
    );
    expect(recordsQuery({ limit: 10, offset: 0, sort: [{ field: "code", direction: "asc" }] })).toContain(
      "sort=code",
    );
  });
  it("passes simple equality filters", () => {
    const q = recordsQuery({ filter: { currency: "USD" } });
    expect(q).toContain("currency=USD");
  });
});
