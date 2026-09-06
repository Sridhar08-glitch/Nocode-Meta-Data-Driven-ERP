import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { PivotRunResult, Report, TableRunResult } from "@/lib/reporting/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const runState = { data: undefined as TableRunResult | PivotRunResult | undefined, isPending: false, isError: false, error: null as unknown, mutate: vi.fn() };
vi.mock("@/lib/reporting/hooks", () => ({ useRunReport: () => runState }));

const { exportCsv, exportXlsx, exportPdf } = vi.hoisted(() => ({
  exportCsv: vi.fn(() => Promise.resolve()),
  exportXlsx: vi.fn(() => Promise.resolve()),
  exportPdf: vi.fn(() => Promise.resolve()),
}));
vi.mock("@/lib/reporting/api", async (orig) => ({
  ...(await orig<typeof import("@/lib/reporting/api")>()),
  reportsApi: { exportCsv, exportXlsx, exportPdf },
}));

import { ReportRuntime } from "./report-runtime";

const report = { id: "r1", name: "Open deals", slug: "open-deals", report_type: "table" } as Report;

beforeEach(() => {
  runState.data = undefined;
  runState.isPending = false;
  runState.isError = false;
  runState.mutate.mockClear();
  vi.clearAllMocks();
});

describe("ReportRuntime", () => {
  it("auto-runs the report on mount", () => {
    render(<ReportRuntime report={report} />);
    expect(runState.mutate).toHaveBeenCalled();
  });

  it("renders a table result with columns + rows", () => {
    runState.data = {
      columns: [{ key: "name", label: "Name" }, { key: "amount", label: "Amount" }],
      rows: [{ name: "Acme", amount: 100 }],
      total_count: 1,
      truncated: false,
    };
    render(<ReportRuntime report={report} />);
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("renders a pivot result matrix", () => {
    runState.data = {
      row_field: "stage",
      column_field: "region",
      agg: "sum",
      row_values: ["open"],
      column_values: ["EU", "US"],
      matrix: [[150, 70]],
    };
    render(<ReportRuntime report={report} />);
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("70")).toBeInTheDocument();
  });

  it("exports to CSV/XLSX/PDF via the api", async () => {
    runState.data = { columns: [{ key: "n", label: "N" }], rows: [{ n: 1 }], total_count: 1, truncated: false };
    render(<ReportRuntime report={report} />);
    fireEvent.click(screen.getByRole("button", { name: "CSV" }));
    fireEvent.click(screen.getByRole("button", { name: "XLSX" }));
    fireEvent.click(screen.getByRole("button", { name: "PDF" }));
    await waitFor(() => expect(exportCsv).toHaveBeenCalledWith("r1", "open-deals"));
    expect(exportXlsx).toHaveBeenCalledWith("r1", "open-deals");
    expect(exportPdf).toHaveBeenCalledWith("r1", "open-deals");
  });

  it("shows an error state when the run fails", () => {
    runState.isError = true;
    render(<ReportRuntime report={report} />);
    expect(screen.getByText("Couldn't run report")).toBeInTheDocument();
  });
});
