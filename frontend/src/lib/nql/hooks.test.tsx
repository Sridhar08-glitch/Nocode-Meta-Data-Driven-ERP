import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({ nqlApi: { query: vi.fn(() => Promise.resolve({ rows: [{ id: "1" }], count: 1 })) } }));

import { nqlApi } from "./api";
import { useRunNql } from "./hooks";
import type { NqlQuery } from "./types";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = "W";
  return { wrapper: Wrapper };
}

const valid: NqlQuery = {
  entity: "deals",
  filter: { op: "and", conditions: [{ field: "status", op: "=", value: "open" }] },
};

beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  tenant.isReady = true;
  vi.clearAllMocks();
});

describe("useRunNql", () => {
  it("runs a valid query", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useRunNql(), { wrapper });
    let res;
    await act(async () => {
      res = await result.current.mutateAsync(valid);
    });
    expect(nqlApi.query).toHaveBeenCalledWith(valid);
    expect(res).toEqual({ rows: [{ id: "1" }], count: 1 });
  });

  it("throws without a workspace", async () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    const { result } = renderHook(() => useRunNql(), { wrapper });
    await expect(result.current.mutateAsync(valid)).rejects.toThrow("No active workspace");
    expect(nqlApi.query).not.toHaveBeenCalled();
  });

  it("throws on an invalid AST before hitting the network", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useRunNql(), { wrapper });
    await expect(result.current.mutateAsync({ entity: "" })).rejects.toThrow("An entity is required.");
    expect(nqlApi.query).not.toHaveBeenCalled();
  });
});
