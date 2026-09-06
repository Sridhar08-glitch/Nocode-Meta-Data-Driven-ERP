"use client";

import { ProjectsNav } from "@/components/projects/projects-nav";
import { ResourcesPanel } from "@/components/projects/resources-panel";

export default function ProjectsResourcesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Resources</h1>
        <p className="text-sm text-muted-foreground">
          Workspace-wide resource utilization, allocation conflicts, and weekly capacity (allocated vs
          available hours). All resourcing math runs server-side.
        </p>
      </div>
      <ProjectsNav />
      <ResourcesPanel />
    </div>
  );
}
