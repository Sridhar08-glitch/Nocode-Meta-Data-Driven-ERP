import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve([])),
  apiSend: vi.fn(() => Promise.resolve({})),
}));

import { apiGet, apiSend } from "@/lib/api/request";

import {
  CARDINALITY_OPTIONS,
  ON_DELETE_OPTIONS,
  relationshipsApi,
} from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("relationshipsApi", () => {
  it("list with no filter hits the collection", () => {
    relationshipsApi.list();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/relationships/");
  });
  it("list with entityId appends the filter", () => {
    relationshipsApi.list("e1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/relationships/?entity_id=e1");
  });
  it("get hits the detail path", () => {
    relationshipsApi.get("r1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/relationships/r1/");
  });
  it("create POSTs", () => {
    relationshipsApi.create({
      name: "Owner",
      slug: "owner",
      source_entity_id: "a",
      target_entity_id: "b",
      cardinality: "one_to_many",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/relationships/", "POST", {
      name: "Owner",
      slug: "owner",
      source_entity_id: "a",
      target_entity_id: "b",
      cardinality: "one_to_many",
    });
  });
  it("remove DELETEs", () => {
    relationshipsApi.remove("r1");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/relationships/r1/", "DELETE");
  });
});

describe("option lists", () => {
  it("expose all four cardinalities and on_delete modes", () => {
    expect(CARDINALITY_OPTIONS.map((o) => o.value)).toEqual([
      "one_to_one",
      "one_to_many",
      "many_to_many",
      "self_ref",
    ]);
    expect(ON_DELETE_OPTIONS.map((o) => o.value)).toContain("cascade");
    expect(ON_DELETE_OPTIONS).toHaveLength(4);
  });
});
