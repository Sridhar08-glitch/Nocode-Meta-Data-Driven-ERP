"use client";

import { useRouter } from "next/navigation";

import { DashboardCreateDialog } from "@/components/reporting/dashboard-create-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { useDashboards } from "@/lib/reporting/hooks";

export default function DashboardsPage() {
  const router = useRouter();
  const dashboards = useDashboards();
  const rows = dashboards.data?.results ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dashboards</h1>
          <p className="text-sm text-muted-foreground">Compose widgets bound to reports.</p>
        </div>
        <DashboardCreateDialog onCreated={(id) => router.push(`/dashboards/${id}`)} />
      </div>

      {dashboards.isLoading && <Skeleton className="h-64 w-full" />}
      {dashboards.isError && <ErrorState title="Couldn't load dashboards" />}
      {dashboards.data && rows.length === 0 && (
        <EmptyState title="No dashboards yet" description="Create your first dashboard." />
      )}

      {rows.length > 0 && (
        <ul className="space-y-2">
          {rows.map((d) => (
            <li key={d.id} className="rounded-md border p-3">
              <button className="text-left font-medium hover:underline" onClick={() => router.push(`/dashboards/${d.id}`)}>
                {d.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
