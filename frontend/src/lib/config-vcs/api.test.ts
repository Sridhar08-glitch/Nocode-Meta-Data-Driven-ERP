import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({})),
  apiSend: vi.fn(() => Promise.resolve({})),
}));

import { apiGet, apiSend } from "@/lib/api/request";

import { configVcsApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("configVcsApi", () => {
  it("commit POSTs message + default branch", () => {
    configVcsApi.commit("Publish leads");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/config-vcs/commit/", "POST", {
      message: "Publish leads",
      branch: "main",
    });
  });
  it("commit honours an explicit branch", () => {
    configVcsApi.commit("x", "draft");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/config-vcs/commit/", "POST", {
      message: "x",
      branch: "draft",
    });
  });
  it("commits GETs with the branch query", () => {
    configVcsApi.commits();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/config-vcs/commits/?branch=main");
  });
  it("diff GETs both shas (encoded)", () => {
    configVcsApi.diff("a b", "c");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/config-vcs/diff/?a=a%20b&b=c");
  });
  it("rollback POSTs the sha", () => {
    configVcsApi.rollback("deadbeef");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/config-vcs/rollback/", "POST", {
      sha: "deadbeef",
    });
  });
});
