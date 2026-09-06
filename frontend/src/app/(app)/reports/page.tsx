"use client";

import { useRouter } from "next/navigation";

import { ReportCreateDialog } from "@/components/reporting/report-create-dialog";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { useReports } from "@/lib/reporting/hooks";

export default function ReportsPage() {
  const router = useRouter();
  const reports = useReports();
  const rows = reports.data?.results ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Reports</h1>
          <p className="text-sm text-muted-foreground">NQL-driven reports with table, pivot, and exports.</p>
        </div>
        <ReportCreateDialog onCreated={(id) => router.push(`/reports/${id}`)} />
      </div>

      {reports.isLoading && <Skeleton className="h-64 w-full" />}
      {reports.isError && <ErrorState title="Couldn't load reports" />}
      {reports.data && rows.length === 0 && <EmptyState title="No reports yet" description="Create your first report." />}

      {rows.length > 0 && (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li key={r.id} className="rounded-md border p-3">
              <button className="flex items-center gap-2 text-left hover:underline" onClick={() => router.push(`/reports/${r.id}`)}>
                <span className="font-medium">{r.name}</span>
                <Badge variant="outline">{r.report_type}</Badge>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
