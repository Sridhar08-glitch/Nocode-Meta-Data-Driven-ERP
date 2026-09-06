import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
  apiSend: vi.fn(() => Promise.resolve({})),
  downloadFile: vi.fn(() => Promise.resolve()),
}));

import { apiGet, apiSend, downloadFile } from "@/lib/api/request";

import { dashboardsApi, isPivotResult, reportsApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
  vi.mocked(downloadFile).mockClear();
});

describe("reportsApi", () => {
  it("CRUD + run + snapshot + validate", () => {
    reportsApi.list("pivot");
    reportsApi.get("r1");
    reportsApi.create({ name: "R", slug: "r", nql_ast: { entity: "deals" } });
    reportsApi.update("r1", { name: "R2" });
    reportsApi.remove("r1");
    reportsApi.run("r1");
    reportsApi.snapshot("r1");
    reportsApi.snapshots("r1");
    reportsApi.validateNql({ nql_source: "status = 'open'" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/reports/?report_type=pivot");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/reports/r1/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/reports/", "POST", { name: "R", slug: "r", nql_ast: { entity: "deals" } });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/reports/r1/", "PATCH", { name: "R2" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/reports/r1/", "DELETE");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/reports/r1/run/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/reports/r1/snapshot/", "POST");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/reports/r1/snapshots/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/reports/validate-nql/", "POST", { nql_source: "status = 'open'" });
  });

  it("downloads exports with the right filenames", () => {
    reportsApi.exportCsv("r1", "deals");
    reportsApi.exportXlsx("r1", "deals");
    reportsApi.exportPdf("r1", "deals");
    expect(downloadFile).toHaveBeenCalledWith("/api/v1/reports/r1/export/csv/", "deals.csv");
    expect(downloadFile).toHaveBeenCalledWith("/api/v1/reports/r1/export/xlsx/", "deals.xlsx");
    expect(downloadFile).toHaveBeenCalledWith("/api/v1/reports/r1/export/pdf/", "deals.pdf");
  });
});

describe("dashboardsApi", () => {
  it("CRUD + nested widgets + run + export", () => {
    dashboardsApi.list();
    dashboardsApi.get("d1");
    dashboardsApi.create({ name: "D", slug: "d" });
    dashboardsApi.update("d1", { name: "D2" });
    dashboardsApi.remove("d1");
    dashboardsApi.run("d1");
    dashboardsApi.exportPdf("d1", "d");
    dashboardsApi.widgets("d1");
    dashboardsApi.createWidget("d1", { widget_type: "metric_card", report_id: "r1" });
    dashboardsApi.updateWidget("d1", "w1", { title: "T" });
    dashboardsApi.deleteWidget("d1", "w1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/dashboards/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/dashboards/", "POST", { name: "D", slug: "d" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/dashboards/d1/run/", "POST");
    expect(downloadFile).toHaveBeenCalledWith("/api/v1/dashboards/d1/export/pdf/", "d.pdf");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/dashboards/d1/widgets/");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/dashboards/d1/widgets/", "POST", {
      widget_type: "metric_card",
      report_id: "r1",
    });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/dashboards/d1/widgets/w1/", "PATCH", { title: "T" });
    expect(apiSend).toHaveBeenCalledWith("/api/v1/dashboards/d1/widgets/w1/", "DELETE");
  });
});

describe("isPivotResult", () => {
  it("discriminates pivot vs table run results", () => {
    expect(isPivotResult({ row_field: "x", column_field: null, agg: "sum", row_values: [], column_values: [], matrix: [] })).toBe(true);
    expect(isPivotResult({ columns: [], rows: [], total_count: 0, truncated: false })).toBe(false);
  });
});
