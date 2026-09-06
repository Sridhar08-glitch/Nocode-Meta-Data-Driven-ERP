import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  savedViewsApi: {
    list: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    create: vi.fn(() => Promise.resolve({ id: "v1" })),
    update: vi.fn(() => Promise.resolve({ id: "v1" })),
    remove: vi.fn(() => Promise.resolve(null)),
  },
}));

import { savedViewsApi } from "./api";
import {
  useCreateSavedView,
  useDeleteSavedView,
  useSavedViews,
  useUpdateSavedView,
} from "./hooks";

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

describe("saved-views hooks", () => {
  it("lists scoped to an entity", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useSavedViews("deals"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(savedViewsApi.list).toHaveBeenCalledWith("deals");
  });

  it("is disabled without a workspace", () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    const { result } = renderHook(() => useSavedViews(), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(savedViewsApi.list).not.toHaveBeenCalled();
  });

  it("create/update/delete call the API and invalidate", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const create = renderHook(() => useCreateSavedView(), { wrapper });
    const update = renderHook(() => useUpdateSavedView(), { wrapper });
    const del = renderHook(() => useDeleteSavedView(), { wrapper });
    await act(async () => {
      await create.result.current.mutateAsync({ entity_slug: "deals", name: "Mine" });
      await update.result.current.mutateAsync({ id: "v1", data: { is_pinned: true } });
      await del.result.current.mutateAsync("v1");
    });
    expect(savedViewsApi.create).toHaveBeenCalledWith({ entity_slug: "deals", name: "Mine" });
    expect(savedViewsApi.update).toHaveBeenCalledWith("v1", { is_pinned: true });
    expect(savedViewsApi.remove).toHaveBeenCalledWith("v1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["saved-views", "acme"] });
  });
});
