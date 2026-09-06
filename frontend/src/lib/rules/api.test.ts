import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })), apiSend: vi.fn(() => Promise.resolve({})) }));
import { apiGet, apiSend } from "@/lib/api/request";
import { rulesApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("rulesApi", () => {
  it("lists (optionally by entity) and CRUDs", () => {
    rulesApi.list();
    rulesApi.list("e1");
    rulesApi.get("r1");
    rulesApi.create({ name: "Auto", slug: "auto", entity_id: "e1", trigger_on: "before_update", actions: [{ type: "set_field", field: "stage", value: "review" }] });
    rulesApi.update("r1", { is_active: false });
    rulesApi.remove("r1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/rules/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/rules/?entity_id=e1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/rules/r1/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/rules/", "POST", {
      name: "Auto",
      slug: "auto",
      entity_id: "e1",
      trigger_on: "before_update",
      actions: [{ type: "set_field", field: "stage", value: "review" }],
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/rules/r1/", "PATCH", { is_active: false });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/rules/r1/", "DELETE");
  });
});
