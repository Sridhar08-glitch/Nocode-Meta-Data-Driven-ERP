import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));

// Source resolution is controlled per-test.
const kind = { current: "system" as "system" | "metadata" };
vi.mock("@/lib/metadata/hooks", () => ({
  useEntityKind: () => ({ kind: kind.current, ready: true }),
}));

vi.mock("@/lib/records/api", () => ({
  recordsApi: { list: vi.fn().mockResolvedValue({ results: [], count: 0 }), get: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn(), restore: vi.fn() },
}));
vi.mock("@/lib/system-entities/api", () => ({
  systemEntitiesApi: {
    list: vi.fn(),
    descriptor: vi.fn(),
    records: {
      list: vi.fn().mockResolvedValue({ results: [{ id: "1" }], count: 1 }),
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      remove: vi.fn(),
    },
  },
}));

import { recordsApi } from "@/lib/records/api";
import { useRecords } from "@/lib/records/hooks";
import { systemEntitiesApi } from "@/lib/system-entities/api";

import { useSystemEntitiesAsMeta } from "./hooks";

function wrap(qc: QueryClient) {
  const W = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  W.displayName = "W";
  return W;
}

const qc = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });

beforeEach(() => vi.clearAllMocks());

describe("source-aware record dispatch (B0.2)", () => {
  it("a system entity routes to the System-Entity records API, NOT /data/", async () => {
    kind.current = "system";
    const { result } = renderHook(() => useRecords("treasury_facility"), { wrapper: wrap(qc()) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(systemEntitiesApi.records.list).toHaveBeenCalledWith("treasury_facility", {});
    expect(recordsApi.list).not.toHaveBeenCalled();
    expect(result.current.data?.count).toBe(1);
  });

  it("a metadata entity routes to /data/, NOT the system API", async () => {
    kind.current = "metadata";
    const { result } = renderHook(() => useRecords("ticket"), { wrapper: wrap(qc()) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(recordsApi.list).toHaveBeenCalledWith("ticket", {});
    expect(systemEntitiesApi.records.list).not.toHaveBeenCalled();
  });
});

describe("backward compatibility", () => {
  it("a system-entities failure degrades to empty + settled (never blocks metadata)", async () => {
    vi.mocked(systemEntitiesApi.list).mockRejectedValueOnce(new Error("no endpoint"));
    const { result } = renderHook(() => useSystemEntitiesAsMeta(), { wrapper: wrap(qc()) });
    await waitFor(() => expect(result.current.settled).toBe(true));
    expect(result.current.data).toEqual([]);
    expect(result.current.isSuccess).toBe(false);
  });
});
