import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SLARecord } from "@/lib/sla/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const slaQ = { isLoading: false, isError: false, data: { results: [] as SLARecord[], count: 0 } };
const pause = { mutateAsync: vi.fn(() => Promise.resolve({ paused: 1, results: [] })), isPending: false };
const resume = { mutateAsync: vi.fn(() => Promise.resolve({ resumed: 1, results: [] })), isPending: false };
vi.mock("@/lib/sla/hooks", () => ({
  useRecordSla: () => slaQ,
  usePauseSla: () => pause,
  useResumeSla: () => resume,
}));

import { RecordSla } from "./record-sla";

function rec(over: Partial<SLARecord> = {}): SLARecord {
  return {
    id: "s1",
    policy_id: "p1",
    entity_id: "e1",
    record_id: "rec1",
    metric_key: "resolution",
    status: "on_track",
    started_at: "2026-01-01T00:00:00Z",
    target_at: "2026-01-02T00:00:00Z",
    warning_at: "2026-01-01T18:00:00Z",
    paused_at: null,
    met_at: null,
    breached_at: null,
    paused_seconds: 0,
    warning_sent: false,
    breach_notified: false,
    ...over,
  };
}

beforeEach(() => {
  slaQ.data = { results: [], count: 0 };
  pause.mutateAsync.mockClear();
  resume.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("RecordSla", () => {
  it("renders nothing when the record has no SLA", () => {
    const { container } = render(<RecordSla entitySlug="tickets" recordId="rec1" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows each metric's status and offers Pause for active SLAs", async () => {
    slaQ.data = { results: [rec({ status: "warning" })], count: 1 };
    render(<RecordSla entitySlug="tickets" recordId="rec1" />);
    expect(screen.getByText("warning")).toBeInTheDocument();
    expect(screen.getByText("resolution")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    await waitFor(() => expect(pause.mutateAsync).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalled();
  });

  it("offers Resume for a paused SLA and not Pause", async () => {
    slaQ.data = { results: [rec({ status: "paused" })], count: 1 };
    render(<RecordSla entitySlug="tickets" recordId="rec1" />);
    expect(screen.queryByRole("button", { name: "Pause" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    await waitFor(() => expect(resume.mutateAsync).toHaveBeenCalled());
  });

  it("shows no actions for a settled (met) SLA", () => {
    slaQ.data = { results: [rec({ status: "met" })], count: 1 };
    render(<RecordSla entitySlug="tickets" recordId="rec1" />);
    expect(screen.queryByRole("button", { name: "Pause" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resume" })).not.toBeInTheDocument();
  });
});
