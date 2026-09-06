import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { LotTrace } from "@/lib/manufacturing/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const createQc = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const createNcr = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const traceQ = { isLoading: false, isError: false, data: undefined as LotTrace | undefined };
let canManage = true;

vi.mock("@/lib/manufacturing/hooks", () => ({
  useCreateQualityCheck: () => createQc,
  useCreateNcr: () => createNcr,
  useLotTrace: () => traceQ,
  useCanManageManufacturing: () => canManage,
}));

import { LotTraceLookup, NcrForm, QualityCheckForm } from "./quality-panel";

beforeEach(() => {
  traceQ.data = undefined;
  canManage = true;
  vi.clearAllMocks();
});

describe("QualityCheckForm", () => {
  it("records a quality check", async () => {
    render(<QualityCheckForm />);
    fireEvent.change(screen.getByLabelText("Production order id"), { target: { value: "mo-1" } });
    fireEvent.change(screen.getByLabelText("Check name"), { target: { value: "Dimensional" } });
    fireEvent.change(screen.getByLabelText("Sampled"), { target: { value: "20" } });
    fireEvent.change(screen.getByLabelText("Passed"), { target: { value: "18" } });
    fireEvent.change(screen.getByLabelText("Failed"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Record check" }));
    await waitFor(() =>
      expect(createQc.mutateAsync).toHaveBeenCalledWith({
        production_order_id: "mo-1", name: "Dimensional", sampled_qty: "20", passed_qty: "18", failed_qty: "2",
      }),
    );
  });

  it("hides the record action for non-admins", () => {
    canManage = false;
    render(<QualityCheckForm />);
    expect(screen.queryByRole("button", { name: "Record check" })).not.toBeInTheDocument();
  });
});

describe("NcrForm", () => {
  it("raises an NCR", async () => {
    render(<NcrForm />);
    fireEvent.change(screen.getByLabelText("Production order id"), { target: { value: "mo-2" } });
    fireEvent.change(screen.getByLabelText("Defect"), { target: { value: "Scratch" } });
    fireEvent.click(screen.getByRole("button", { name: "Raise NCR" }));
    await waitFor(() =>
      expect(createNcr.mutateAsync).toHaveBeenCalledWith({ production_order_id: "mo-2", defect: "Scratch" }),
    );
  });
});

describe("LotTraceLookup", () => {
  it("traces a lot and renders the result", async () => {
    traceQ.data = {
      lot: { id: "lot-1", number: "LOT-1" },
      production_order: { id: "mo-1", number: "MO-0001" },
      components: [{ item_id: "comp-1" }],
      consumed_lots: [],
    };
    render(<LotTraceLookup />);
    fireEvent.change(screen.getByLabelText("Lot id"), { target: { value: "lot-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
    await waitFor(() => expect(screen.getByText(/Components \(1\)/)).toBeInTheDocument());
    expect(screen.getByText(/Consumed lots \(0\)/)).toBeInTheDocument();
  });
});

describe("QualityCheckForm + NcrForm coexisting", () => {
  it("each form targets its own production order field", () => {
    render(
      <>
        <QualityCheckForm />
        <NcrForm />
      </>,
    );
    const orderInputs = screen.getAllByLabelText("Production order id");
    expect(orderInputs).toHaveLength(2);
    const qcSection = orderInputs[0].closest("div.rounded-lg") as HTMLElement;
    expect(within(qcSection).getByText("Quality check")).toBeInTheDocument();
  });
});
