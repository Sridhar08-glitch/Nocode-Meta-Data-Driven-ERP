import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({ apiGet: vi.fn(() => Promise.resolve({})) }));
import { apiGet } from "@/lib/api/request";
import { lineageApi } from "./api";

beforeEach(() => vi.mocked(apiGet).mockClear());

describe("lineageApi", () => {
  it("lists nodes (optionally filtered) and traverses both directions", () => {
    lineageApi.listNodes();
    lineageApi.listNodes("entity");
    lineageApi.upstream("n1", 3);
    lineageApi.downstream("n1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/lineage/nodes/");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/lineage/nodes/?node_type=entity");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/lineage/nodes/n1/upstream/?max_depth=3");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/lineage/nodes/n1/downstream/?max_depth=5");
  });
});
