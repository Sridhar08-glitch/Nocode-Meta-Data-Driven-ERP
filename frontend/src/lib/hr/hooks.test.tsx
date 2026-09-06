import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  hrApi: {
    setup: vi.fn(() => Promise.resolve({ detail: "ok" })),
    createDocument: vi.fn(() => Promise.resolve({ id: "r1", number: "CAN-0001" })),
    hireCandidate: vi.fn(() => Promise.resolve({ candidate: { id: "c1" }, employee: { id: "e1", number: "EMP-0001" } })),
    completeInterview: vi.fn(() => Promise.resolve({ id: "i1", status: "completed" })),
    acceptOffer: vi.fn(() => Promise.resolve({ id: "o1", status: "accepted" })),
    approveLeave: vi.fn(() => Promise.resolve({ id: "lr1", status: "approved" })),
    rejectLeave: vi.fn(() => Promise.resolve({ id: "lr2", status: "rejected" })),
    completePerformance: vi.fn(() => Promise.resolve({ id: "pr1", status: "completed" })),
    promoteEmployee: vi.fn(() => Promise.resolve({ id: "e1" })),
    transferEmployee: vi.fn(() => Promise.resolve({ id: "e1" })),
    offboardEmployee: vi.fn(() => Promise.resolve({ id: "e1", status: "terminated" })),
  },
}));

import { hrApi } from "./api";
import {
  useAcceptOffer,
  useApproveLeave,
  useCompleteInterview,
  useCompletePerformance,
  useCreateDocument,
  useEnsureSetup,
  useHireCandidate,
  useOffboardEmployee,
  usePromoteEmployee,
  useRejectLeave,
  useTransferEmployee,
} from "./hooks";

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}
function wrap(qc: QueryClient) {
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = "TestWrapper";
  return Wrapper;
}

beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  tenant.isReady = true;
  vi.clearAllMocks();
});

describe("HR lifecycle hooks", () => {
  it("useEnsureSetup calls setup", async () => {
    const { result } = renderHook(() => useEnsureSetup(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(hrApi.setup).toHaveBeenCalledTimes(1);
  });

  it("useCreateDocument creates with entity slug + data", async () => {
    const { result } = renderHook(() => useCreateDocument(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync({ entitySlug: "candidate", data: { full_name: "Ada" } });
    });
    expect(hrApi.createDocument).toHaveBeenCalledWith("candidate", { full_name: "Ada" });
  });

  it("useHireCandidate hires by record id and invalidates record + entity caches", async () => {
    const qc = client();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useHireCandidate(), { wrapper: wrap(qc) });
    await act(async () => {
      await result.current.mutateAsync("c1");
    });
    expect(hrApi.hireCandidate).toHaveBeenCalledWith("c1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["data", "acme"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["entities", "acme"] });
  });

  it("useCompleteInterview completes by record id", async () => {
    const { result } = renderHook(() => useCompleteInterview(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync("i1");
    });
    expect(hrApi.completeInterview).toHaveBeenCalledWith("i1");
  });

  it("useAcceptOffer accepts by record id", async () => {
    const { result } = renderHook(() => useAcceptOffer(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync("o1");
    });
    expect(hrApi.acceptOffer).toHaveBeenCalledWith("o1");
  });

  it("useApproveLeave approves by record id", async () => {
    const { result } = renderHook(() => useApproveLeave(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync("lr1");
    });
    expect(hrApi.approveLeave).toHaveBeenCalledWith("lr1");
  });

  it("useRejectLeave rejects by record id", async () => {
    const { result } = renderHook(() => useRejectLeave(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync("lr2");
    });
    expect(hrApi.rejectLeave).toHaveBeenCalledWith("lr2");
  });

  it("useCompletePerformance completes by record id", async () => {
    const { result } = renderHook(() => useCompletePerformance(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync("pr1");
    });
    expect(hrApi.completePerformance).toHaveBeenCalledWith("pr1");
  });

  it("usePromoteEmployee promotes with record id + new position", async () => {
    const { result } = renderHook(() => usePromoteEmployee(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync({ recordId: "e1", newPosition: "pos9" });
    });
    expect(hrApi.promoteEmployee).toHaveBeenCalledWith("e1", "pos9");
  });

  it("useTransferEmployee transfers with record id + new department", async () => {
    const { result } = renderHook(() => useTransferEmployee(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync({ recordId: "e1", newDepartment: "dep4" });
    });
    expect(hrApi.transferEmployee).toHaveBeenCalledWith("e1", "dep4");
  });

  it("useOffboardEmployee offboards by record id and invalidates the record caches", async () => {
    const qc = client();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useOffboardEmployee(), { wrapper: wrap(qc) });
    await act(async () => {
      await result.current.mutateAsync("e1");
    });
    expect(hrApi.offboardEmployee).toHaveBeenCalledWith("e1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["data", "acme"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["entities", "acme"] });
  });
});
