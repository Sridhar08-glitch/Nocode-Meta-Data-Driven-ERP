import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  rulesApi: {
    list: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    create: vi.fn(() => Promise.resolve({ id: "r1" })),
    update: vi.fn(() => Promise.resolve({})),
    remove: vi.fn(() => Promise.resolve(null)),
  },
}));
import { rulesApi } from "./api";
import { useCreateRule, useDeleteRule, useRules, useUpdateRule } from "./hooks";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const W = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  W.displayName = "W";
  return { qc, wrapper: W };
}
beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  tenant.isReady = true;
  vi.clearAllMocks();
});

describe("rules hooks", () => {
  it("lists filtered by entity, idle without workspace", async () => {
    const { wrapper } = wrap();
    const r = renderHook(() => useRules("e1"), { wrapper });
    await waitFor(() => expect(r.result.current.isSuccess).toBe(true));
    expect(rulesApi.list).toHaveBeenCalledWith("e1");
    tenant.workspace = null;
    const { wrapper: w2 } = wrap();
    expect(renderHook(() => useRules(), { wrapper: w2 }).result.current.fetchStatus).toBe("idle");
  });

  it("create/update/delete invalidate the rules root", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const c = renderHook(() => useCreateRule(), { wrapper });
    const u = renderHook(() => useUpdateRule(), { wrapper });
    const d = renderHook(() => useDeleteRule(), { wrapper });
    await act(async () => {
      await c.result.current.mutateAsync({ name: "A", slug: "a" });
      await u.result.current.mutateAsync({ id: "r1", data: { priority: 5 } });
      await d.result.current.mutateAsync("r1");
    });
    expect(rulesApi.create).toHaveBeenCalled();
    expect(rulesApi.update).toHaveBeenCalledWith("r1", { priority: 5 });
    expect(rulesApi.remove).toHaveBeenCalledWith("r1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["rules", "acme"] });
  });
});
