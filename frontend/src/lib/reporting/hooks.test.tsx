import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  reportsApi: {
    list: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    get: vi.fn(() => Promise.resolve({})),
    create: vi.fn(() => Promise.resolve({ id: "r1" })),
    update: vi.fn(() => Promise.resolve({})),
    remove: vi.fn(() => Promise.resolve(null)),
    run: vi.fn(() => Promise.resolve({ columns: [], rows: [], total_count: 0, truncated: false })),
    validateNql: vi.fn(() => Promise.resolve({ valid: true, errors: [] })),
  },
  dashboardsApi: {
    list: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    get: vi.fn(() => Promise.resolve({})),
    create: vi.fn(() => Promise.resolve({ id: "d1" })),
    remove: vi.fn(() => Promise.resolve(null)),
    run: vi.fn(() => Promise.resolve({ dashboard_id: "d1", name: "D", widgets: [] })),
    createWidget: vi.fn(() => Promise.resolve({})),
    updateWidget: vi.fn(() => Promise.resolve({})),
    deleteWidget: vi.fn(() => Promise.resolve(null)),
  },
}));

import { dashboardsApi, reportsApi } from "./api";
import {
  useCreateDashboard,
  useCreateReport,
  useCreateWidget,
  useDeleteWidget,
  useReports,
  useRunDashboard,
  useRunReport,
  useUpdateWidget,
  useValidateNql,
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

describe("reporting query hooks", () => {
  it("fetches reports when scoped, idle without a workspace", async () => {
    const { wrapper } = wrap();
    const r = renderHook(() => useReports("pivot"), { wrapper });
    await waitFor(() => expect(r.result.current.isSuccess).toBe(true));
    expect(reportsApi.list).toHaveBeenCalledWith("pivot");

    tenant.workspace = null;
    const { wrapper: w2 } = wrap();
    const r2 = renderHook(() => useReports(), { wrapper: w2 });
    expect(r2.result.current.fetchStatus).toBe("idle");
  });
});

describe("reporting mutations", () => {
  it("runs a report and validates NQL (mutations, no invalidate needed)", async () => {
    const { wrapper } = wrap();
    const run = renderHook(() => useRunReport("r1"), { wrapper });
    const val = renderHook(() => useValidateNql(), { wrapper });
    await act(async () => {
      await run.result.current.mutateAsync();
      await val.result.current.mutateAsync({ nql_source: "x = 1" });
    });
    expect(reportsApi.run).toHaveBeenCalled();
    expect(reportsApi.validateNql).toHaveBeenCalledWith({ nql_source: "x = 1" });
  });

  it("create report/dashboard invalidate their roots", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const cr = renderHook(() => useCreateReport(), { wrapper });
    const cd = renderHook(() => useCreateDashboard(), { wrapper });
    await act(async () => {
      await cr.result.current.mutateAsync({ name: "R", slug: "r", nql_ast: {} });
      await cd.result.current.mutateAsync({ name: "D", slug: "d" });
    });
    expect(reportsApi.create).toHaveBeenCalled();
    expect(dashboardsApi.create).toHaveBeenCalled();
    expect(spy).toHaveBeenCalledWith({ queryKey: ["reports", "acme"] });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["dashboards", "acme"] });
  });

  it("widget CRUD + dashboard run target the right dashboard", async () => {
    const { wrapper } = wrap();
    const create = renderHook(() => useCreateWidget("d1"), { wrapper });
    const update = renderHook(() => useUpdateWidget("d1"), { wrapper });
    const del = renderHook(() => useDeleteWidget("d1"), { wrapper });
    const run = renderHook(() => useRunDashboard("d1"), { wrapper });
    await act(async () => {
      await create.result.current.mutateAsync({ widget_type: "report", report_id: "r1" });
      await update.result.current.mutateAsync({ wid: "w1", data: { title: "T" } });
      await del.result.current.mutateAsync("w1");
      await run.result.current.mutateAsync();
    });
    expect(dashboardsApi.createWidget).toHaveBeenCalledWith("d1", { widget_type: "report", report_id: "r1" });
    expect(dashboardsApi.updateWidget).toHaveBeenCalledWith("d1", "w1", { title: "T" });
    expect(dashboardsApi.deleteWidget).toHaveBeenCalledWith("d1", "w1");
    expect(dashboardsApi.run).toHaveBeenCalled();
  });
});
