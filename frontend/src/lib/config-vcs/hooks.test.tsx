import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  configVcsApi: {
    commits: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    commit: vi.fn(() => Promise.resolve({ sha: "abc" })),
    rollback: vi.fn(() => Promise.resolve({ sha: "def" })),
  },
}));

import { configVcsApi } from "./api";
import { useCommits, usePublish, useRollback } from "./hooks";

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = "W";
  return { qc, wrapper: Wrapper };
}

beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  tenant.isReady = true;
  vi.clearAllMocks();
});

describe("config-vcs hooks", () => {
  it("useCommits fetches the branch", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useCommits(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(configVcsApi.commits).toHaveBeenCalledWith("main");
  });

  it("useCommits is disabled without a workspace", () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    const { result } = renderHook(() => useCommits(), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(configVcsApi.commits).not.toHaveBeenCalled();
  });

  it("usePublish commits and invalidates both config-vcs and meta", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => usePublish(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ message: "Publish" });
    });
    expect(configVcsApi.commit).toHaveBeenCalledWith("Publish", undefined);
    expect(spy).toHaveBeenCalledWith({ queryKey: ["config-vcs", "acme"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["meta", "acme"] });
  });

  it("useRollback calls rollback with the sha", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useRollback(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("deadbeef");
    });
    expect(configVcsApi.rollback).toHaveBeenCalledWith("deadbeef");
  });
});
