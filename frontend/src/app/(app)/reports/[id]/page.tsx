"use client";

import Link from "next/link";

import { ReportRuntime } from "@/components/reporting/report-runtime";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { useReport } from "@/lib/reporting/hooks";

export default function ReportDetailPage({ params }: { params: { id: string } }) {
  const report = useReport(params.id);
  return (
    <div className="space-y-4">
      <Link href="/reports" className="text-sm text-muted-foreground hover:underline">
        ← Reports
      </Link>
      {report.isLoading && <Skeleton className="h-64 w-full" />}
      {report.isError && <ErrorState title="Report not found" />}
      {report.data && <ReportRuntime report={report.data} />}
    </div>
  );
}
