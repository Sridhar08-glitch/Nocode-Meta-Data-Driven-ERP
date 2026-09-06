import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ProjectSchedule } from "@/lib/projects/api";

const schedQ = { isLoading: false, isError: false, data: null as ProjectSchedule | null };
vi.mock("@/lib/projects/hooks", () => ({
  useProjectSchedule: () => schedQ,
}));

import { ScheduleView } from "./schedule-panel";

const schedule = (over: Partial<ProjectSchedule> = {}): ProjectSchedule => ({
  project_duration: 30,
  critical_task_ids: ["task-abc12345", "task-def67890"],
  total_float: 5,
  earliest_finish: "2026-07-15",
  gantt: [
    { id: "task-abc12345", start: "2026-06-01", finish: "2026-06-10", float: 0, critical: true },
    { id: "task-xyz00000", start: "2026-06-05", finish: "2026-06-12", float: 3, critical: false },
  ],
  ...over,
});

beforeEach(() => {
  schedQ.data = null;
  schedQ.isLoading = false;
  schedQ.isError = false;
  vi.clearAllMocks();
});

describe("ScheduleView", () => {
  it("renders the critical-path summary + gantt from query data", () => {
    schedQ.data = schedule();
    render(<ScheduleView projectRecordId="pr-1" />);
    expect(screen.getByText("30 days")).toBeInTheDocument(); // duration
    expect(screen.getByText("5 days")).toBeInTheDocument(); // total float
    expect(screen.getByText("2026-07-15")).toBeInTheDocument(); // earliest finish
    // gantt rows render
    expect(screen.getByText("2026-06-10")).toBeInTheDocument();
    expect(screen.getAllByText("Critical").length).toBeGreaterThan(0);
  });

  it("shows an empty gantt state when no tasks are scheduled", () => {
    schedQ.data = schedule({ gantt: [], critical_task_ids: [] });
    render(<ScheduleView projectRecordId="pr-1" />);
    expect(screen.getByText("No scheduled tasks")).toBeInTheDocument();
  });

  it("surfaces a load error", () => {
    schedQ.isError = true;
    render(<ScheduleView projectRecordId="pr-1" />);
    expect(screen.getByText("Couldn't load schedule")).toBeInTheDocument();
  });
});
