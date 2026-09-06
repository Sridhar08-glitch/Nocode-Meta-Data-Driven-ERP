import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Dashboard, Report } from "@/lib/reporting/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const createReport = { mutateAsync: vi.fn(() => Promise.resolve({ id: "r9", name: "R" })), isPending: false };
const validate = { mutateAsync: vi.fn(() => Promise.resolve({ valid: true, errors: [] as string[] })), isPending: false };
const createWidget = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const deleteWidget = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/reporting/hooks", () => ({
  useCreateReport: () => createReport,
  useValidateNql: () => validate,
  useCreateWidget: () => createWidget,
  useDeleteWidget: () => deleteWidget,
}));

import { DashboardBuilder } from "./dashboard-builder";
import { ReportCreateDialog } from "./report-create-dialog";

beforeEach(() => {
  createReport.mutateAsync.mockClear().mockResolvedValue({ id: "r9", name: "R" });
  validate.mutateAsync.mockClear().mockResolvedValue({ valid: true, errors: [] });
  createWidget.mutateAsync.mockClear().mockResolvedValue({});
  deleteWidget.mutateAsync.mockClear().mockResolvedValue(null);
  vi.clearAllMocks();
});

describe("ReportCreateDialog", () => {
  it("validates the NQL then creates the report with a derived slug + type", async () => {
    const onCreated = vi.fn();
    render(<ReportCreateDialog onCreated={onCreated} />);
    fireEvent.click(screen.getByRole("button", { name: "New report" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Open Deals" } });
    fireEvent.change(screen.getByLabelText(/NQL/), { target: { value: "status = 'open'" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(validate.mutateAsync).toHaveBeenCalledWith({ nql_source: "status = 'open'" }));
    await waitFor(() =>
      expect(createReport.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Open Deals", slug: "open_deals", report_type: "table", nql_source: "status = 'open'" }),
      ),
    );
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("r9"));
  });

  it("blocks creation and shows errors when the NQL is invalid", async () => {
    validate.mutateAsync.mockResolvedValueOnce({ valid: false, errors: ["bad token"] });
    render(<ReportCreateDialog />);
    fireEvent.click(screen.getByRole("button", { name: "New report" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Bad" } });
    fireEvent.change(screen.getByLabelText(/NQL/), { target: { value: "???" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(screen.getByText("bad token")).toBeInTheDocument());
    expect(createReport.mutateAsync).not.toHaveBeenCalled();
  });
});

describe("DashboardBuilder", () => {
  const reports = [{ id: "r1", name: "Deals" }] as Report[];
  const dashboard = {
    id: "d1",
    widgets: [{ id: "w1", widget_type: "text", title: "Note", grid_w: 6 }],
  } as unknown as Dashboard;

  it("adds a report-bound widget with its grid width", async () => {
    render(<DashboardBuilder dashboard={dashboard} reports={reports} />);
    fireEvent.click(screen.getByRole("button", { name: "Add widget" }));
    // default type is "report" → needs a report binding (Create gated until chosen)
    fireEvent.click(screen.getByRole("combobox", { name: /Report$/i }));
    fireEvent.click(await screen.findByRole("option", { name: "Deals" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Pipeline" } });
    fireEvent.click(screen.getByRole("button", { name: "Add widget" }));
    await waitFor(() =>
      expect(createWidget.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ widget_type: "report", report_id: "r1", title: "Pipeline", grid_w: 6 }),
      ),
    );
  });

  it("removes a widget", async () => {
    render(<DashboardBuilder dashboard={dashboard} reports={reports} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove widget Note" }));
    await waitFor(() => expect(deleteWidget.mutateAsync).toHaveBeenCalledWith("w1"));
  });
});
