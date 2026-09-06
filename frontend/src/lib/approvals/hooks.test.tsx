import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  approvalsApi: {
    listProcesses: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    createProcess: vi.fn(() => Promise.resolve({ id: "p1" })),
    deleteProcess: vi.fn(() => Promise.resolve(null)),
    pendingForMe: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    approve: vi.fn(() => Promise.resolve({})),
    reject: vi.fn(() => Promise.resolve({})),
  },
}));
import { approvalsApi } from "./api";
import { useApprovalProcesses, useApproveRequest, useCreateProcess, usePendingApprovals, useRejectRequest } from "./hooks";

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

describe("approvals hooks", () => {
  it("fetches processes + pending, creates a process", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const procs = renderHook(() => useApprovalProcesses(), { wrapper });
    const pending = renderHook(() => usePendingApprovals(), { wrapper });
    await waitFor(() => expect(procs.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(pending.result.current.isSuccess).toBe(true));
    const create = renderHook(() => useCreateProcess(), { wrapper });
    await act(async () => {
      await create.result.current.mutateAsync({ name: "P", slug: "p" });
    });
    expect(approvalsApi.createProcess).toHaveBeenCalled();
    expect(spy).toHaveBeenCalledWith({ queryKey: ["approvals", "acme"] });
  });

  it("approve/reject thread the comment + invalidate", async () => {
    const { wrapper } = wrap();
    const a = renderHook(() => useApproveRequest(), { wrapper });
    const r = renderHook(() => useRejectRequest(), { wrapper });
    await act(async () => {
      await a.result.current.mutateAsync({ id: "req1", comment: "ok" });
      await r.result.current.mutateAsync({ id: "req2", comment: "no" });
    });
    expect(approvalsApi.approve).toHaveBeenCalledWith("req1", "ok");
    expect(approvalsApi.reject).toHaveBeenCalledWith("req2", "no");
  });
});
