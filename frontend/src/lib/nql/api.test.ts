import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({})),
  apiSend: vi.fn(() => Promise.resolve({ rows: [], count: 0 })),
}));

import { apiSend } from "@/lib/api/request";

import { nqlApi } from "./api";

beforeEach(() => vi.mocked(apiSend).mockClear());

describe("nqlApi", () => {
  it("POSTs the serialized wire AST to the query endpoint", () => {
    nqlApi.query({
      entity: "deals",
      select: [],
      filter: { op: "and", conditions: [{ field: "status", op: "in", value: "open" }] },
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/nql/query/", "POST", {
      entity: "deals",
      filter: { op: "and", conditions: [{ field: "status", op: "in", value: ["open"] }] },
    });
  });
});
