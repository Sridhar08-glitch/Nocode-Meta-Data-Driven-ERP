import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Timeline } from "@/lib/activity/api";

const tl = { isLoading: false, isError: false, data: undefined as Timeline | undefined };
vi.mock("@/lib/activity/hooks", () => ({ useRecordTimeline: () => tl }));

import { RecordPlayback } from "./record-playback";

const timeline: Timeline = {
  events: [
    { event_type: "record.created", version: 1, occurred_at: "2026-01-01T00:00:00Z", actor_id: "u1", changed_fields: ["name"] },
    { event_type: "record.updated", version: 2, occurred_at: "2026-01-02T00:00:00Z", actor_id: "u1", changed_fields: ["stage"] },
    { event_type: "record.updated", version: 3, occurred_at: "2026-01-03T00:00:00Z", actor_id: "u2", changed_fields: ["amount"] },
  ],
  count: 3,
};

beforeEach(() => {
  tl.data = undefined;
  tl.isLoading = false;
  tl.isError = false;
  vi.clearAllMocks();
});

describe("RecordPlayback", () => {
  it("starts at the first event and accumulates touched fields as you scrub forward", () => {
    tl.data = timeline;
    render(<RecordPlayback entitySlug="deals" recordId="r1" />);
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
    expect(screen.getByText("record.created")).toBeInTheDocument();
    expect(screen.getByText("Fields touched through this step (1)")).toBeInTheDocument();

    // step to the end → all three fields touched
    fireEvent.change(screen.getByLabelText("History step"), { target: { value: "2" } });
    expect(screen.getByText("3 / 3")).toBeInTheDocument();
    expect(screen.getByText("record.updated")).toBeInTheDocument();
    expect(screen.getByText("Fields touched through this step (3)")).toBeInTheDocument();
  });

  it("steps with the next/prev buttons", () => {
    tl.data = timeline;
    render(<RecordPlayback entitySlug="deals" recordId="r1" />);
    fireEvent.click(screen.getByRole("button", { name: "Next step" }));
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Previous step" }));
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
  });

  it("shows an empty state for a record with no history", () => {
    tl.data = { events: [], count: 0 };
    render(<RecordPlayback entitySlug="deals" recordId="r1" />);
    expect(screen.getByText("No history")).toBeInTheDocument();
  });
});
