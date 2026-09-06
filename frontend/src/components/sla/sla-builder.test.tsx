import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SLAPolicy } from "@/lib/sla/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));
vi.mock("@/lib/metadata/hooks", () => ({ useEntities: () => ({ data: [{ id: "e1", name: "Tickets", slug: "tickets" }] }) }));

const dashQ = { data: { breached: 2, warning: 1, on_track: 5, met: 9, paused: 0 } };
const policiesQ = { isLoading: false, isError: false, data: { results: [] as SLAPolicy[], count: 0 } };
const create = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
const del = { mutateAsync: vi.fn(() => Promise.resolve(null)), isPending: false };
vi.mock("@/lib/sla/hooks", () => ({
  useSlaDashboard: () => dashQ,
  useSlaPolicies: () => policiesQ,
  useCreatePolicy: () => create,
  useDeletePolicy: () => del,
}));

import { SlaBuilder } from "./sla-builder";

beforeEach(() => {
  policiesQ.data = { results: [], count: 0 };
  create.mutateAsync.mockClear().mockResolvedValue({});
  del.mutateAsync.mockClear().mockResolvedValue(null);
  vi.clearAllMocks();
});

describe("SlaBuilder", () => {
  it("shows the dashboard status counts", () => {
    render(<SlaBuilder />);
    expect(within(screen.getByLabelText("breached")).getByText("2")).toBeInTheDocument();
    expect(within(screen.getByLabelText("met")).getByText("9")).toBeInTheDocument();
  });

  it("creates a policy with a target", async () => {
    render(<SlaBuilder />);
    fireEvent.click(screen.getAllByRole("button", { name: "New policy" })[0]);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Support" } });
    fireEvent.click(screen.getByRole("combobox", { name: "Entity" }));
    fireEvent.click(await screen.findByRole("option", { name: "Tickets" }));
    fireEvent.change(screen.getByLabelText("Target 1 metric"), { target: { value: "first_response" } });
    fireEvent.change(screen.getByLabelText("Target 1 minutes"), { target: { value: "60" } });
    fireEvent.click(screen.getByRole("button", { name: "Create policy" }));
    await waitFor(() => expect(create.mutateAsync).toHaveBeenCalled());
    expect(create.mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Support",
        slug: "support",
        entity_id: "e1",
        targets: [expect.objectContaining({ metric: "first_response", target_minutes: 60, warning_at_percent: 80 })],
      }),
    );
  });

  it("deletes a policy", async () => {
    policiesQ.data = { results: [{ id: "p1", name: "Old", targets: [], is_active: true } as unknown as SLAPolicy], count: 1 };
    render(<SlaBuilder />);
    fireEvent.click(screen.getByRole("button", { name: "Remove policy Old" }));
    await waitFor(() => expect(del.mutateAsync).toHaveBeenCalledWith("p1"));
  });
});
