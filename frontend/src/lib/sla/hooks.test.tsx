import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  slaApi: {
    listPolicies: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    createPolicy: vi.fn(() => Promise.resolve({ id: "p1" })),
    listBusinessHours: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    createBusinessHours: vi.fn(() => Promise.resolve({ id: "b1" })),
    dashboard: vi.fn(() => Promise.resolve({ breached: 0, warning: 0, on_track: 0, met: 0, paused: 0 })),
    recordStatus: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    pause: vi.fn(() => Promise.resolve({ paused: 1, results: [] })),
    resume: vi.fn(() => Promise.resolve({ resumed: 1, results: [] })),
  },
}));
import { slaApi } from "./api";
import {
  useBusinessHours,
  useCreatePolicy,
  usePauseSla,
  useRecordSla,
  useResumeSla,
  useSlaDashboard,
  useSlaPolicies,
} from "./hooks";

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

describe("sla hooks", () => {
  it("fetches policies, business-hours, dashboard, record status", async () => {
    const { wrapper } = wrap();
    const p = renderHook(() => useSlaPolicies(), { wrapper });
    const b = renderHook(() => useBusinessHours(), { wrapper });
    const d = renderHook(() => useSlaDashboard(), { wrapper });
    const rec = renderHook(() => useRecordSla("tickets", "rec1"), { wrapper });
    await waitFor(() => expect(p.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(b.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(d.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(rec.result.current.isSuccess).toBe(true));
    expect(slaApi.recordStatus).toHaveBeenCalledWith("tickets", "rec1");
  });

  it("creates a policy (invalidates) and pause/resume target the record", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const create = renderHook(() => useCreatePolicy(), { wrapper });
    const pause = renderHook(() => usePauseSla("tickets", "rec1"), { wrapper });
    const resume = renderHook(() => useResumeSla("tickets", "rec1"), { wrapper });
    await act(async () => {
      await create.result.current.mutateAsync({ name: "S", slug: "s" });
      await pause.result.current.mutateAsync();
      await resume.result.current.mutateAsync();
    });
    expect(slaApi.createPolicy).toHaveBeenCalled();
    expect(slaApi.pause).toHaveBeenCalledWith("tickets", "rec1");
    expect(slaApi.resume).toHaveBeenCalledWith("tickets", "rec1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["sla", "acme"] });
  });
});
