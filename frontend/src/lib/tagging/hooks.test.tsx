import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  tagsApi: {
    list: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    create: vi.fn(() => Promise.resolve({ id: "t1" })),
    forRecord: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    attach: vi.fn(() => Promise.resolve({ detail: "attached" })),
    detach: vi.fn(() => Promise.resolve({ removed: 1 })),
  },
}));
import { tagsApi } from "./api";
import { useAttachTag, useDetachTag, useRecordTags, useTags } from "./hooks";

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

describe("tagging hooks", () => {
  it("lists workspace tags + a record's tags", async () => {
    const { wrapper } = wrap();
    const all = renderHook(() => useTags(), { wrapper });
    const rec = renderHook(() => useRecordTags("r1"), { wrapper });
    await waitFor(() => expect(all.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(rec.result.current.isSuccess).toBe(true));
    expect(tagsApi.forRecord).toHaveBeenCalledWith("r1");
  });
  it("attach/detach target the record + invalidate its tag list", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const attach = renderHook(() => useAttachTag("deals", "r1"), { wrapper });
    const detach = renderHook(() => useDetachTag("r1"), { wrapper });
    await act(async () => {
      await attach.result.current.mutateAsync("t1");
      await detach.result.current.mutateAsync("t1");
    });
    expect(tagsApi.attach).toHaveBeenCalledWith("deals", "t1", "r1");
    expect(tagsApi.detach).toHaveBeenCalledWith("t1", "r1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["tags", "acme", "record", "r1"] });
  });
});
