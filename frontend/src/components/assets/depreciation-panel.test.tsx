import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DepreciationSchedule } from "@/lib/assets/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const schedulesQ = { isLoading: false, isError: false, data: [] as DepreciationSchedule[] };
const entriesQ = { isLoading: false, isError: false, data: [] as { period_index: number; amount: string; accumulated: string; net_book_value: string }[] };
const createSchedule = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const runDep = { mutateAsync: vi.fn(() => Promise.resolve({ period_index: 1, amount: "100", accumulated: "100", net_book_value: "900" })), isPending: false };
const runAll = { mutateAsync: vi.fn(() => Promise.resolve({ posted: 3 })), isPending: false };
const preview = { mutateAsync: vi.fn(() => Promise.resolve([{ period_index: 1, amount: "100", accumulated: "100", net_book_value: "900" }])), isPending: false };

vi.mock("@/lib/assets/hooks", () => ({
  useSchedules: () => schedulesQ,
  useScheduleEntries: () => entriesQ,
  useCreateSchedule: () => createSchedule,
  useRunDepreciation: () => runDep,
  useRunAllDepreciation: () => runAll,
  useDepreciationPreview: () => preview,
}));

import { CreateScheduleForm, PreviewForm, SchedulesList } from "./depreciation-panel";

const schedule = (over: Partial<DepreciationSchedule> = {}): DepreciationSchedule => ({
  id: "s1", asset_record_id: "asset-1234-5678", method: "straight_line",
  acquisition_cost: "1000", salvage_value: "100", useful_life_months: 60, start_date: "2026-01-01",
  status: "active", ...over,
});

const arg = (v: unknown) => v as never;

beforeEach(() => {
  schedulesQ.data = [];
  entriesQ.data = [];
  vi.clearAllMocks();
});

describe("CreateScheduleForm", () => {
  it("creates a schedule with the typed parameters", async () => {
    render(<CreateScheduleForm />);
    fireEvent.change(screen.getByLabelText("Asset record id"), { target: { value: "asset-1" } });
    fireEvent.change(screen.getByLabelText("Acquisition cost"), { target: { value: "10000" } });
    fireEvent.change(screen.getByLabelText("Salvage value"), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("Useful life (months)"), { target: { value: "60" } });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));
    await waitFor(() =>
      expect(createSchedule.mutateAsync).toHaveBeenCalledWith(
        arg(
          expect.objectContaining({
            asset_record_id: "asset-1",
            method: "straight_line",
            acquisition_cost: "10000",
            salvage_value: "500",
            useful_life_months: 60,
          }),
        ),
      ),
    );
  });

  it("rejects a non-positive useful life", async () => {
    render(<CreateScheduleForm />);
    fireEvent.change(screen.getByLabelText("Asset record id"), { target: { value: "asset-1" } });
    fireEvent.change(screen.getByLabelText("Acquisition cost"), { target: { value: "10000" } });
    fireEvent.change(screen.getByLabelText("Useful life (months)"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Create schedule" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(createSchedule.mutateAsync).not.toHaveBeenCalled();
  });
});

describe("SchedulesList", () => {
  it("prompts to create a schedule when none exist", () => {
    render(<SchedulesList canManage />);
    expect(screen.getByText("No depreciation schedules")).toBeInTheDocument();
  });

  it("runs a period against a schedule", async () => {
    schedulesQ.data = [schedule()];
    render(<SchedulesList canManage />);
    fireEvent.click(screen.getByRole("button", { name: "Run period" }));
    await waitFor(() =>
      expect(runDep.mutateAsync).toHaveBeenCalledWith(arg(expect.objectContaining({ scheduleId: "s1" }))),
    );
    expect(toast.success).toHaveBeenCalled();
  });

  it("runs all schedules for admins and reports the count", async () => {
    schedulesQ.data = [schedule()];
    render(<SchedulesList canManage />);
    fireEvent.click(screen.getByRole("button", { name: "Run all (today)" }));
    await waitFor(() => expect(runAll.mutateAsync).toHaveBeenCalled());
    expect(toast.success).toHaveBeenCalledWith("Posted 3 entries");
  });

  it("hides Run all for non-admins", () => {
    schedulesQ.data = [schedule()];
    render(<SchedulesList canManage={false} />);
    expect(screen.queryByRole("button", { name: "Run all (today)" })).not.toBeInTheDocument();
  });

  it("shows posted entries when a schedule is expanded", async () => {
    schedulesQ.data = [schedule()];
    entriesQ.data = [{ period_index: 1, amount: "100", accumulated: "100", net_book_value: "900" }];
    render(<SchedulesList canManage />);
    fireEvent.click(screen.getByRole("button", { name: "Schedule s1" }));
    await waitFor(() => expect(screen.getByText("900")).toBeInTheDocument());
  });
});

describe("PreviewForm", () => {
  it("computes and renders a no-write preview", async () => {
    render(<PreviewForm />);
    fireEvent.change(screen.getByLabelText("Acquisition cost"), { target: { value: "10000" } });
    fireEvent.change(screen.getByLabelText("Useful life (months)"), { target: { value: "60" } });
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() =>
      expect(preview.mutateAsync).toHaveBeenCalledWith(
        arg(expect.objectContaining({ method: "straight_line", acquisition_cost: "10000", useful_life_months: 60 })),
      ),
    );
    expect(await screen.findByText("900")).toBeInTheDocument();
  });
});
