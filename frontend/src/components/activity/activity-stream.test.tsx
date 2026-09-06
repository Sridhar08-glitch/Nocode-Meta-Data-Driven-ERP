import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ActivityEntry } from "@/lib/activity/api";

const feed = vi.fn();
const feedState = { isLoading: false, isError: false, data: { results: [] as ActivityEntry[], count: 0 } };
vi.mock("@/lib/activity/hooks", () => ({ useActivityFeed: (p: unknown) => { feed(p); return feedState; } }));

import { ActivityStream } from "./activity-stream";

function entry(over: Partial<ActivityEntry> = {}): ActivityEntry {
  return {
    id: "a1",
    entity_id: "e1",
    record_id: "r1",
    activity_type: "field_changed",
    actor_id: "u1",
    actor_type: "user",
    actor_name: "Alice",
    summary: "updated the deal",
    changes: [{ field_slug: "status", field_label: "Status", old: "open", new: "won" }],
    event_sequence: 5,
    occurred_at: "2026-03-01T10:00:00Z",
    is_pinned: false,
    ...over,
  };
}

beforeEach(() => {
  feedState.data = { results: [], count: 0 };
  feedState.isLoading = false;
  feedState.isError = false;
  vi.clearAllMocks();
});

describe("ActivityStream", () => {
  it("renders entries with the field diff (old → new)", () => {
    feedState.data = { results: [entry()], count: 1 };
    render(<ActivityStream />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText(/Status/)).toBeInTheDocument();
    expect(screen.getByText(/open → won/)).toBeInTheDocument();
  });

  it("passes the type + date filters to the feed query", async () => {
    render(<ActivityStream />);
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "comment_added" } });
    await waitFor(() =>
      expect(feed).toHaveBeenCalledWith(expect.objectContaining({ activity_type: "comment_added", limit: 100 })),
    );
  });

  it("shows the empty state with no activity", () => {
    render(<ActivityStream />);
    expect(screen.getByText("No activity")).toBeInTheDocument();
  });
});
