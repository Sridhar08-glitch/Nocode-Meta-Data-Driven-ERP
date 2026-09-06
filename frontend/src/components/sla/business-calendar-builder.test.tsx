import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BusinessHours } from "@/lib/sla/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const calQ = { isLoading: false, isError: false, data: { results: [] as BusinessHours[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/sla/hooks", () => ({
  useBusinessHours: () => calQ,
  useCreateBusinessHours: () => create,
  useUpdateBusinessHours: () => update,
}));

import { BusinessCalendarBuilder } from "./business-calendar-builder";

const cal = (over: Partial<BusinessHours> = {}): BusinessHours => ({
  id: "c1",
  name: "EMEA",
  timezone: "Europe/Paris",
  schedule: {},
  weekly_hours: { mon: [{ start: "09:00", end: "17:00" }], tue: [], wed: [], thu: [], fri: [], sat: [], sun: [] },
  shifts: {},
  holidays: [{ date: "2026-12-25", name: "Christmas" }],
  region: "EMEA",
  created_at: "",
  updated_at: "",
  ...over,
});

beforeEach(() => {
  calQ.data = { results: [], count: 0 };
  create.mutateAsync.mockClear();
  update.mutateAsync.mockClear();
  vi.clearAllMocks();
});

describe("BusinessCalendarBuilder", () => {
  it("lists calendars with timezone + working-day summary", () => {
    calQ.data = { results: [cal()], count: 1 };
    render(<BusinessCalendarBuilder />);
    expect(screen.getByText("EMEA")).toBeInTheDocument();
    expect(screen.getByText("Europe/Paris")).toBeInTheDocument();
    expect(screen.getByText(/1 working day/)).toBeInTheDocument();
  });

  it("creates a calendar with default Mon–Fri weekly hours + combobox timezone", async () => {
    render(<BusinessCalendarBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New calendar" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "US East" } });
    // timezone is now a searchable combobox
    fireEvent.click(screen.getByRole("combobox", { name: "Timezone" }));
    fireEvent.change(await screen.findByLabelText("Timezone search"), { target: { value: "New_York" } });
    fireEvent.click(await screen.findByRole("option", { name: "America/New_York" }));
    fireEvent.click(screen.getByRole("button", { name: "Create calendar" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    const arg = (create.mutateAsync.mock.calls[0] as unknown[])[0] as {
      name: string; timezone: string; weekly_hours: Record<string, unknown[]>;
    };
    expect(arg.name).toBe("US East");
    expect(arg.timezone).toBe("America/New_York");
    expect(arg.weekly_hours.mon).toHaveLength(1);
    expect(arg.weekly_hours.sat).toHaveLength(0);
  });

  it("disables save until a name is entered", () => {
    render(<BusinessCalendarBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New calendar" })[0]);
    expect(screen.getByRole("button", { name: "Create calendar" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Ops" } });
    expect(screen.getByRole("button", { name: "Create calendar" })).toBeEnabled();
  });

  it("blocks save on an invalid interval (start ≥ end) with an inline error", () => {
    render(<BusinessCalendarBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New calendar" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Bad" } });
    fireEvent.change(screen.getByLabelText("Monday shift 1 start"), { target: { value: "18:00" } });
    expect(screen.getByText(/must be before end/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create calendar" })).toBeDisabled();
  });

  it("adds a split shift to a working day", async () => {
    render(<BusinessCalendarBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New calendar" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Split" } });
    fireEvent.click(screen.getByRole("button", { name: "Add interval to Monday" }));
    expect(screen.getByLabelText("Monday shift 2 start")).toBeInTheDocument();
    // give the second shift non-overlapping evening hours (overlap would be rejected by validation)
    fireEvent.change(screen.getByLabelText("Monday shift 2 start"), { target: { value: "18:00" } });
    fireEvent.change(screen.getByLabelText("Monday shift 2 end"), { target: { value: "20:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Create calendar" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    const arg = (create.mutateAsync.mock.calls[0] as unknown[])[0] as { weekly_hours: Record<string, unknown[]> };
    expect(arg.weekly_hours.mon).toHaveLength(2);
  });

  it("adds a holiday row and persists it on save", async () => {
    render(<BusinessCalendarBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New calendar" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "With holiday" } });
    fireEvent.click(screen.getByRole("button", { name: "Add holiday" }));
    fireEvent.change(screen.getByLabelText("Holiday 1 date"), { target: { value: "2026-07-04" } });
    fireEvent.change(screen.getByLabelText("Holiday 1 name"), { target: { value: "Independence Day" } });
    fireEvent.click(screen.getByRole("button", { name: "Create calendar" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    const arg = (create.mutateAsync.mock.calls[0] as unknown[])[0] as { holidays: { date: string; name?: string }[] };
    expect(arg.holidays).toEqual([{ date: "2026-07-04", name: "Independence Day" }]);
  });

  it("edits an existing calendar", async () => {
    calQ.data = { results: [cal()], count: 1 };
    render(<BusinessCalendarBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Edit calendar EMEA" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "EMEA West" } });
    fireEvent.click(screen.getByRole("button", { name: "Save calendar" }));
    await waitFor(() => expect(update.mutateAsync).toHaveBeenCalled());
    expect(update.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ id: "c1", data: expect.objectContaining({ name: "EMEA West" }) }),
    );
  });
});
