import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Kpi } from "@/lib/analytics/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const kpisQ = { isLoading: false, isError: false, data: [] as Kpi[] };
const create = { mutateAsync: vi.fn(() => Promise.resolve({ id: "k9" })), isPending: false };
const update = { mutateAsync: vi.fn(() => Promise.resolve({ id: "k1" })), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve()), isPending: false };
let canManage = true;

vi.mock("@/lib/analytics/hooks", () => ({
  useKpis: () => kpisQ,
  useCreateKpi: () => create,
  useUpdateKpi: () => update,
  useDeleteKpi: () => del,
  useCanManageAnalytics: () => canManage,
}));

import { KpiRegistry } from "./kpi-registry";

const kpi = (over: Partial<Kpi> = {}): Kpi => ({
  id: "k1",
  code: "gross_margin",
  name: "Gross margin",
  description: "",
  category: "finance",
  source_type: "nql",
  nql_source: "invoice",
  value_field: "amount",
  aggregate: "sum",
  native_key: "",
  target: "40",
  warning_threshold: "35",
  critical_threshold: null,
  direction: "higher_better",
  unit: "%",
  owner: "",
  refresh_strategy: "on_read",
  is_active: true,
  is_system: false,
  ...over,
});

beforeEach(() => {
  kpisQ.data = [];
  canManage = true;
  vi.clearAllMocks();
});

describe("KpiRegistry", () => {
  it("renders the KPI table", () => {
    kpisQ.data = [kpi()];
    render(<KpiRegistry />);
    expect(screen.getByText("gross_margin")).toBeInTheDocument();
    expect(screen.getByText("Gross margin")).toBeInTheDocument();
    expect(screen.getByText("finance")).toBeInTheDocument();
  });

  it("marks system KPIs read-only", () => {
    kpisQ.data = [kpi({ is_system: true })];
    render(<KpiRegistry />);
    expect(screen.getByText("system")).toBeInTheDocument();
    expect(screen.getByText("read-only")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("creates an NQL KPI with the source-specific payload", async () => {
    render(<KpiRegistry />);
    fireEvent.click(screen.getAllByRole("button", { name: "New KPI" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Paid invoices" } });
    fireEvent.change(within(dialog).getByLabelText("Category"), { target: { value: "finance" } });
    fireEvent.change(within(dialog).getByLabelText("NQL source"), { target: { value: "invoice where paid" } });
    fireEvent.change(within(dialog).getByLabelText("Value field"), { target: { value: "amount" } });
    fireEvent.change(within(dialog).getByLabelText("Target"), { target: { value: "1000" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          code: "paid_invoices",
          name: "Paid invoices",
          category: "finance",
          source_type: "nql",
          nql_source: "invoice where paid",
          value_field: "amount",
          aggregate: "sum",
          target: "1000",
          direction: "higher_better",
        }),
      ),
    );
    // NQL variant must NOT send a native_key.
    const nqlPayload = (create.mutateAsync.mock.calls as unknown[][])[0][0];
    expect(nqlPayload).not.toHaveProperty("native_key");
  });

  it("creates a native KPI when source type is switched to native", async () => {
    render(<KpiRegistry />);
    fireEvent.click(screen.getAllByRole("button", { name: "New KPI" })[0]);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Uptime" } });
    fireEvent.change(within(dialog).getByLabelText("Category"), { target: { value: "it" } });
    // switch source type to native
    fireEvent.click(within(dialog).getByLabelText("Source type"));
    fireEvent.click(await screen.findByRole("option", { name: "Native key" }));
    fireEvent.change(within(dialog).getByLabelText("Native key"), { target: { value: "system_uptime" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(create.mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          code: "uptime",
          source_type: "native",
          native_key: "system_uptime",
        }),
      ),
    );
    const nativePayload = (create.mutateAsync.mock.calls as unknown[][])[0][0];
    expect(nativePayload).not.toHaveProperty("nql_source");
  });

  it("deletes a KPI", async () => {
    kpisQ.data = [kpi()];
    render(<KpiRegistry />);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("k1"));
  });

  it("hides create + actions for non-admins", () => {
    canManage = false;
    kpisQ.data = [kpi()];
    render(<KpiRegistry />);
    expect(screen.queryByRole("button", { name: "New KPI" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });
});
