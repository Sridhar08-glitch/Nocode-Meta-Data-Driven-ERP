"use client";

import Link from "next/link";

import { DashboardBuilder } from "@/components/reporting/dashboard-builder";
import { DashboardRuntime } from "@/components/reporting/dashboard-runtime";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDashboard, useReports } from "@/lib/reporting/hooks";

export default function DashboardDetailPage({ params }: { params: { id: string } }) {
  const dashboard = useDashboard(params.id);
  const reports = useReports();

  return (
    <div className="space-y-4">
      <Link href="/dashboards" className="text-sm text-muted-foreground hover:underline">
        ← Dashboards
      </Link>
      {dashboard.isLoading && <Skeleton className="h-64 w-full" />}
      {dashboard.isError && <ErrorState title="Dashboard not found" />}
      {dashboard.data && (
        <Tabs defaultValue="view">
          <TabsList>
            <TabsTrigger value="view">Dashboard</TabsTrigger>
            <TabsTrigger value="build">Builder</TabsTrigger>
          </TabsList>
          <TabsContent value="view" className="pt-4">
            <DashboardRuntime dashboard={dashboard.data} />
          </TabsContent>
          <TabsContent value="build" className="pt-4">
            <DashboardBuilder dashboard={dashboard.data} reports={reports.data?.results ?? []} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
