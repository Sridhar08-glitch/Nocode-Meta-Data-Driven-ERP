import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ListColumn } from "@/lib/records/columns";

import { DataTable } from "./data-table";

const columns: ListColumn[] = [
  { slug: "name", label: "Name", fieldType: "text", sortable: true },
  { slug: "active", label: "Active", fieldType: "boolean", sortable: false },
];
const rows = [
  { id: "1", name: "Acme", active: true },
  { id: "2", name: "Globex", active: false },
];

function setup(over: Partial<React.ComponentProps<typeof DataTable>> = {}) {
  const props = {
    columns,
    rows,
    sort: null,
    onSort: vi.fn(),
    selected: new Set<string>(),
    onToggleRow: vi.fn(),
    onToggleAll: vi.fn(),
    onRowClick: vi.fn(),
    ...over,
  };
  render(<DataTable {...props} />);
  return props;
}

describe("DataTable", () => {
  it("renders formatted cells (boolean → Yes/No)", () => {
    setup();
    expect(screen.getByText("Acme")).toBeInTheDocument();
    expect(screen.getByText("Yes")).toBeInTheDocument();
    expect(screen.getByText("No")).toBeInTheDocument();
  });

  it("only sortable columns have a sort control", () => {
    setup();
    expect(screen.getByRole("button", { name: /Name/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Active/ })).not.toBeInTheDocument();
  });

  it("clicking a sortable header calls onSort", () => {
    const p = setup();
    fireEvent.click(screen.getByRole("button", { name: /Name/ }));
    expect(p.onSort).toHaveBeenCalledWith("name");
  });

  it("toggles a row without triggering row navigation", () => {
    const p = setup();
    const firstRow = screen.getAllByRole("row")[1];
    fireEvent.click(within(firstRow).getByLabelText("Select row"));
    expect(p.onToggleRow).toHaveBeenCalledWith("1");
    expect(p.onRowClick).not.toHaveBeenCalled();
  });

  it("clicking a row navigates", () => {
    const p = setup();
    fireEvent.click(screen.getByText("Acme"));
    expect(p.onRowClick).toHaveBeenCalledWith("1");
  });

  it("select-all reflects state and fires onToggleAll", () => {
    const p = setup({ selected: new Set(["1", "2"]) });
    const selectAll = screen.getByLabelText("Select all rows");
    expect(selectAll).toBeChecked();
    fireEvent.click(selectAll);
    expect(p.onToggleAll).toHaveBeenCalled();
  });
});
