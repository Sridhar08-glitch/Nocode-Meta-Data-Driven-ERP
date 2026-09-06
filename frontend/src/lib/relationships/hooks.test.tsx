import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  relationshipsApi: {
    list: vi.fn(() => Promise.resolve([])),
    create: vi.fn(() => Promise.resolve({ id: "r1" })),
    remove: vi.fn(() => Promise.resolve(null)),
  },
}));

import { relationshipsApi } from "./api";
import { useCreateRelationship, useDeleteRelationship, useRelationships } from "./hooks";

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = "W";
  return { wrapper: Wrapper };
}

beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  tenant.isReady = true;
  vi.clearAllMocks();
});

describe("relationship hooks", () => {
  it("useRelationships fetches (optionally filtered)", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useRelationships("e1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(relationshipsApi.list).toHaveBeenCalledWith("e1");
  });

  it("useRelationships fetches all when unfiltered", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useRelationships(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(relationshipsApi.list).toHaveBeenCalledWith(undefined);
  });

  it("is disabled without a workspace", () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    const { result } = renderHook(() => useRelationships("e1"), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(relationshipsApi.list).not.toHaveBeenCalled();
  });

  it("useCreateRelationship posts the body", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useCreateRelationship(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        name: "Owner",
        slug: "owner",
        source_entity_id: "a",
        target_entity_id: "b",
        cardinality: "one_to_many",
      });
    });
    expect(relationshipsApi.create).toHaveBeenCalled();
  });

  it("useDeleteRelationship removes by id", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useDeleteRelationship(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("r1");
    });
    expect(relationshipsApi.remove).toHaveBeenCalledWith("r1");
  });
});
