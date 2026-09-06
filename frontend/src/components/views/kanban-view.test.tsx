import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Row } from "@/lib/views/types";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

import { KanbanView } from "./kanban-view";

const rows: Row[] = [
  { id: "1", name: "Acme", stage: "open" },
  { id: "2", name: "Globex", stage: "won" },
];

function setup(onMove = vi.fn(() => Promise.resolve({}))) {
  render(
    <KanbanView
      rows={rows}
      groupField="stage"
      order={["open", "won"]}
      titleField="name"
      onMove={onMove}
    />,
  );
  return onMove;
}

function column(label: RegExp) {
  return screen.getByRole("listitem", { name: label });
}

beforeEach(() => vi.clearAllMocks());

describe("KanbanView", () => {
  it("renders status columns with their cards", () => {
    setup();
    expect(within(column(/^open \(1\)/)).getByText("Acme")).toBeInTheDocument();
    expect(within(column(/^won \(1\)/)).getByText("Globex")).toBeInTheDocument();
  });

  it("optimistically moves a card and persists the field patch", async () => {
    const onMove = setup();
    fireEvent.click(screen.getByRole("combobox", { name: "Move Acme" }));
    fireEvent.click(await screen.findByRole("option", { name: "won" }));
    // optimistic: Acme now lives in the won column (count 2) immediately
    await waitFor(() => expect(column(/^won \(2\)/)).toBeInTheDocument());
    expect(onMove).toHaveBeenCalledWith("1", { stage: "won" });
  });

  it("rolls back the move when the mutation fails", async () => {
    const onMove = vi.fn(() => Promise.reject(new Error("boom")));
    setup(onMove);
    fireEvent.click(screen.getByRole("combobox", { name: "Move Acme" }));
    fireEvent.click(await screen.findByRole("option", { name: "won" }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    // rolled back: open column has its card again
    expect(within(column(/^open \(1\)/)).getByText("Acme")).toBeInTheDocument();
    expect(column(/^won \(1\)/)).toBeInTheDocument();
  });
});
