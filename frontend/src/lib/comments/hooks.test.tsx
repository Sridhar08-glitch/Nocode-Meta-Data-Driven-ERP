import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  commentsApi: {
    list: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    create: vi.fn(() => Promise.resolve({})),
    edit: vi.fn(() => Promise.resolve({})),
    remove: vi.fn(() => Promise.resolve(null)),
    pin: vi.fn(() => Promise.resolve({})),
    unpin: vi.fn(() => Promise.resolve({})),
  },
}));
import { commentsApi } from "./api";
import { useComments, useCreateComment, useDeleteComment, useEditComment, useTogglePin } from "./hooks";

function wrap() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const W = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  W.displayName = "W";
  return { qc, wrapper: W };
}
beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  vi.clearAllMocks();
});

describe("comment hooks", () => {
  it("lists scoped to the record", async () => {
    const { wrapper } = wrap();
    const r = renderHook(() => useComments("deals", "r1"), { wrapper });
    await waitFor(() => expect(r.result.current.isSuccess).toBe(true));
    expect(commentsApi.list).toHaveBeenCalledWith("deals", "r1");
  });
  it("create/edit/delete/pin invalidate the record's comment list", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const c = renderHook(() => useCreateComment("deals", "r1"), { wrapper });
    const e = renderHook(() => useEditComment("deals", "r1"), { wrapper });
    const d = renderHook(() => useDeleteComment("deals", "r1"), { wrapper });
    const p = renderHook(() => useTogglePin("deals", "r1"), { wrapper });
    await act(async () => {
      await c.result.current.mutateAsync({ body: "hi @[u1]" });
      await e.result.current.mutateAsync({ id: "c1", body: "x" });
      await d.result.current.mutateAsync("c1");
      await p.result.current.mutateAsync({ id: "c1", pinned: false });
    });
    expect(commentsApi.create).toHaveBeenCalledWith("deals", "r1", { body: "hi @[u1]" });
    expect(commentsApi.edit).toHaveBeenCalledWith("deals", "r1", "c1", "x");
    expect(commentsApi.remove).toHaveBeenCalledWith("deals", "r1", "c1");
    expect(commentsApi.pin).toHaveBeenCalledWith("deals", "r1", "c1"); // pinned:false → pin
    expect(spy).toHaveBeenCalledWith({ queryKey: ["comments", "acme", "deals", "r1"] });
  });
});
