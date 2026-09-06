import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { EntityMeta, FieldMeta } from "@/lib/metadata/types";
import type { Row } from "@/lib/views/types";

import { ViewSwitcher } from "./view-switcher";

function field(slug: string, t: string): FieldMeta {
  return { slug, name: slug, field_type: t } as unknown as FieldMeta;
}
const entity = {
  id: "e1",
  slug: "deals",
  title_field_slug: "name",
  fields: [field("name", "text"), field("stage", "select"), field("due", "date"), field("amount", "currency")],
} as unknown as EntityMeta;

const rows: Row[] = [
  { id: "1", name: "Acme", stage: "open", due: "2026-03-01", amount: 100 },
  { id: "2", name: "Globex", stage: "won", due: "2026-03-02", amount: 50 },
];

describe("ViewSwitcher", () => {
  it("shows configuration errors for an invalid definition", () => {
    render(<ViewSwitcher definition={{ kind: "kanban", config: {} }} rows={rows} entity={entity} />);
    expect(screen.getByText("This view needs configuration:")).toBeInTheDocument();
    expect(screen.getByText("Group field is required.")).toBeInTheDocument();
  });

  it("dispatches to the matching view for a valid definition", () => {
    render(
      <ViewSwitcher definition={{ kind: "pivot", config: { rowField: "stage", colField: "stage", agg: "count" } }} rows={rows} entity={entity} />,
    );
    expect(screen.getByRole("table")).toBeInTheDocument(); // pivot renders a table
  });

  it("wires optimistic updates through the shared onUpdate (kanban move)", async () => {
    const onUpdate = vi.fn(() => Promise.resolve({}));
    render(
      <ViewSwitcher
        definition={{ kind: "kanban", config: { groupField: "stage", titleField: "name", order: ["open", "won"] } }}
        rows={rows}
        entity={entity}
        onUpdate={onUpdate}
      />,
    );
    fireEvent.click(screen.getByRole("combobox", { name: "Move Acme" }));
    fireEvent.click(await screen.findByRole("option", { name: "won" }));
    await waitFor(() => expect(onUpdate).toHaveBeenCalledWith("1", { stage: "won" }));
  });

  it("renders the chart engine from the same rows", () => {
    render(
      <ViewSwitcher
        definition={{ kind: "chart", config: { chartType: "bar", groupField: "stage", valueField: "amount", agg: "sum" } }}
        rows={rows}
        entity={entity}
      />,
    );
    // the F2.2 chart engine renders a figure + accessible data table with the aggregated value
    expect(screen.getByRole("figure", { name: "Bar chart" })).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("100")).toBeInTheDocument(); // Acme amount (open)
  });
});
