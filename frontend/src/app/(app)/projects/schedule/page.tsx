"use client";

import { ProjectsNav } from "@/components/projects/projects-nav";
import { SchedulePanel } from "@/components/projects/schedule-panel";

export default function ProjectsSchedulePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Schedule</h1>
        <p className="text-sm text-muted-foreground">
          Critical path, total float, and a gantt view for a project. The forward/backward pass and
          critical-path computation run server-side.
        </p>
      </div>
      <ProjectsNav />
      <SchedulePanel />
    </div>
  );
}
