import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Row } from "@/lib/views/types";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

import { CalendarView } from "./calendar-view";

const rows: Row[] = [{ id: "1", name: "Call Acme", due: "2026-03-10" }];

function setup(onReschedule = vi.fn(() => Promise.resolve({}))) {
  render(
    <CalendarView
      rows={rows}
      dateField="due"
      titleField="name"
      year={2026}
      month={2}
      onReschedule={onReschedule}
    />,
  );
  return onReschedule;
}

beforeEach(() => vi.clearAllMocks());

describe("CalendarView", () => {
  it("places an event on its day cell", () => {
    setup();
    const cell = screen.getByLabelText("2026-03-10");
    expect(within(cell).getByText("Call Acme")).toBeInTheDocument();
  });

  it("optimistically reschedules and persists the date patch", async () => {
    const onReschedule = setup();
    fireEvent.change(screen.getByLabelText("Reschedule Call Acme"), { target: { value: "2026-03-20" } });
    await waitFor(() => expect(onReschedule).toHaveBeenCalledWith("1", { due: "2026-03-20" }));
    // optimistic: the event now lives on the 20th
    expect(within(screen.getByLabelText("2026-03-20")).getByText("Call Acme")).toBeInTheDocument();
  });

  it("rolls back when the reschedule fails", async () => {
    setup(vi.fn(() => Promise.reject(new Error("nope"))));
    fireEvent.change(screen.getByLabelText("Reschedule Call Acme"), { target: { value: "2026-03-20" } });
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    // back on the original day
    expect(within(screen.getByLabelText("2026-03-10")).getByText("Call Acme")).toBeInTheDocument();
  });
});
