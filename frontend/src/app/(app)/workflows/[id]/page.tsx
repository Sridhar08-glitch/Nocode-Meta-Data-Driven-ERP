"use client";

import Link from "next/link";

import { RunMonitor } from "@/components/workflows/run-monitor";
import { WorkflowDesigner } from "@/components/workflows/workflow-designer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function WorkflowDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  return (
    <div className="space-y-4">
      <Link href="/workflows" className="text-sm text-muted-foreground hover:underline">
        ← Workflows
      </Link>
      <Tabs defaultValue="designer">
        <TabsList>
          <TabsTrigger value="designer">Designer</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
        </TabsList>
        <TabsContent value="designer" className="pt-4">
          <WorkflowDesigner definitionId={id} />
        </TabsContent>
        <TabsContent value="runs" className="pt-4">
          <RunMonitor definitionId={id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
