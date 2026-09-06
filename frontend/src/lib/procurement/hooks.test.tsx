import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  procurementApi: {
    setup: vi.fn(() => Promise.resolve({ detail: "ok" })),
    createDocument: vi.fn(() => Promise.resolve({ id: "r1", number: "RFQ-0001" })),
    approveDocument: vi.fn(() => Promise.resolve({ id: "r1", status: "approved" })),
    postGoodsReceipt: vi.fn(() => Promise.resolve({ id: "gr1", status: "posted" })),
    postVendorBill: vi.fn(() => Promise.resolve({ id: "vb1", status: "posted" })),
  },
}));

import { procurementApi } from "./api";
import {
  useApproveDocument,
  useCreateDocument,
  useEnsureSetup,
  usePostGoodsReceipt,
  usePostVendorBill,
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

describe("procurement lifecycle hooks", () => {
  it("useEnsureSetup calls setup", async () => {
    const { result } = renderHook(() => useEnsureSetup(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(procurementApi.setup).toHaveBeenCalledTimes(1);
  });

  it("useCreateDocument creates with entity slug + data", async () => {
    const { result } = renderHook(() => useCreateDocument(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync({ entitySlug: "rfq", data: { vendor: "v1" } });
    });
    expect(procurementApi.createDocument).toHaveBeenCalledWith("rfq", { vendor: "v1" });
  });

  it("useApproveDocument approves with entity slug + record id", async () => {
    const { result } = renderHook(() => useApproveDocument(), { wrapper: wrap(client()) });
    await act(async () => {
      await result.current.mutateAsync({ entitySlug: "purchase_order", recordId: "po1" });
    });
    expect(procurementApi.approveDocument).toHaveBeenCalledWith("purchase_order", "po1");
  });

  it("usePostGoodsReceipt posts by record id and invalidates records + inventory", async () => {
    const qc = client();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => usePostGoodsReceipt(), { wrapper: wrap(qc) });
    await act(async () => {
      await result.current.mutateAsync("gr1");
    });
    expect(procurementApi.postGoodsReceipt).toHaveBeenCalledWith("gr1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["data", "acme"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["entities", "acme"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["inventory", "acme"] });
  });

  it("usePostVendorBill posts by record id and invalidates the record caches", async () => {
    const qc = client();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => usePostVendorBill(), { wrapper: wrap(qc) });
    await act(async () => {
      await result.current.mutateAsync("vb1");
    });
    expect(procurementApi.postVendorBill).toHaveBeenCalledWith("vb1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["data", "acme"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["entities", "acme"] });
  });
});
