"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { isPivotResult, type PivotRunResult, type Report, reportsApi, type TableRunResult } from "@/lib/reporting/api";
import { useRunReport } from "@/lib/reporting/hooks";

/** Report runtime (Phase F2.3): runs a report and renders the table or pivot result + exports. */
export function ReportRuntime({ report }: { report: Report }) {
  const run = useRunReport(report.id);
  const { mutate } = run;

  useEffect(() => {
    mutate();
  }, [mutate]);

  async function exportAs(kind: "csv" | "xlsx" | "pdf") {
    try {
      if (kind === "csv") await reportsApi.exportCsv(report.id, report.slug);
      else if (kind === "xlsx") await reportsApi.exportXlsx(report.id, report.slug);
      else await reportsApi.exportPdf(report.id, report.slug);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Export failed");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">{report.name}</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={run.isPending}>
            {run.isPending ? "Running…" : "Run"}
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportAs("csv")}>
            CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportAs("xlsx")}>
            XLSX
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportAs("pdf")}>
            PDF
          </Button>
        </div>
      </div>

      {run.isPending && !run.data && <Skeleton className="h-64 w-full" />}
      {run.isError && <ErrorState title="Couldn't run report" description={(run.error as ApiError)?.message} />}
      {run.data &&
        (isPivotResult(run.data) ? <PivotResultTable result={run.data} /> : <TableResult result={run.data} />)}
    </div>
  );
}

function TableResult({ result }: { result: TableRunResult }) {
  if (result.rows.length === 0) return <EmptyState title="No rows" />;
  return (
    <div className="space-y-1 overflow-x-auto">
      {result.truncated && (
        <p className="text-xs text-muted-foreground">Showing the first {result.total_count} rows (truncated).</p>
      )}
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            {result.columns.map((c) => (
              <th key={c.key} className="px-3 py-1 text-left font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i} className="border-b">
              {result.columns.map((c) => (
                <td key={c.key} className="px-3 py-1">
                  {row[c.key] === null || row[c.key] === undefined ? "—" : String(row[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PivotResultTable({ result }: { result: PivotRunResult }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-1 text-left font-medium">
              {result.row_field} \ {result.agg}
            </th>
            {result.column_values.map((cv) => (
              <th key={cv} className="px-3 py-1 text-right font-medium">
                {cv}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.row_values.map((rv, i) => (
            <tr key={rv} className="border-b">
              <th className="px-3 py-1 text-left font-medium">{rv}</th>
              {result.column_values.map((cv, j) => (
                <td key={cv} className="px-3 py-1 text-right tabular-nums">
                  {result.matrix[i]?.[j] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
