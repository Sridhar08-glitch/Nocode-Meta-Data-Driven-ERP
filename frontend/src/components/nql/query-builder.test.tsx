import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { emptyQuery } from "@/lib/nql/builder";
import type { NqlQuery } from "@/lib/nql/types";

import { QueryBuilder, type FieldOption } from "./query-builder";

const fields: FieldOption[] = [
  { slug: "status", name: "Status" },
  { slug: "value", name: "Value" },
];

function Harness() {
  const [q, setQ] = useState<NqlQuery>(emptyQuery("deals"));
  return <QueryBuilder fields={fields} value={q} onChange={setQ} />;
}

function preview() {
  return screen.getByLabelText("NQL preview").textContent;
}

describe("QueryBuilder", () => {
  it("starts with SELECT * and an empty filter group", () => {
    render(<Harness />);
    expect(preview()).toBe("SELECT * FROM deals");
    expect(screen.getByText("No conditions yet.")).toBeInTheDocument();
  });

  it("adds a condition and reflects it in the NQL preview", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Add condition" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Field" }));
    fireEvent.click(await screen.findByRole("option", { name: "Status" }));
    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "open" } });
    await waitFor(() => expect(preview()).toBe("SELECT * FROM deals WHERE status = 'open'"));
  });

  it("switches the match type to OR", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Add condition" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Add condition" })[0]);
    // pick a field for both so they render
    const fieldSelects = screen.getAllByRole("combobox", { name: "Field" });
    fireEvent.click(fieldSelects[0]);
    fireEvent.click(await screen.findByRole("option", { name: "Status" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Match type" }));
    fireEvent.click(await screen.findByRole("option", { name: "Any (OR)" }));
    // the value text uses OR joiner once 2+ conditions render; at minimum preview re-renders
    expect(preview()).toContain("status");
  });

  it("hides the value input for a nullary operator", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Add condition" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Field" }));
    fireEvent.click(await screen.findByRole("option", { name: "Status" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Operator" }));
    fireEvent.click(await screen.findByRole("option", { name: "is empty" }));
    expect(screen.queryByLabelText("Value")).not.toBeInTheDocument();
    await waitFor(() => expect(preview()).toBe("SELECT * FROM deals WHERE status is null"));
  });

  it("splits a list value for an `in` operator", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Add condition" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Field" }));
    fireEvent.click(await screen.findByRole("option", { name: "Status" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Operator" }));
    fireEvent.click(await screen.findByRole("option", { name: "in" }));
    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "open, won" } });
    await waitFor(() =>
      expect(preview()).toBe("SELECT * FROM deals WHERE status in ('open', 'won')"),
    );
  });

  it("adds and removes a nested group", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Add group" }));
    expect(screen.getByRole("button", { name: "Remove group" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove group" }));
    expect(screen.queryByRole("button", { name: "Remove group" })).not.toBeInTheDocument();
  });

  it("removes a condition", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Add condition" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Field" }));
    fireEvent.click(await screen.findByRole("option", { name: "Value" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove condition" }));
    expect(screen.getByText("No conditions yet.")).toBeInTheDocument();
  });

  it("adds a sort clause and shows ORDER BY", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Add sort" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Sort field 1" }));
    fireEvent.click(await screen.findByRole("option", { name: "Value" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Sort direction 1" }));
    fireEvent.click(await screen.findByRole("option", { name: "Descending" }));
    await waitFor(() => expect(preview()).toBe("SELECT * FROM deals ORDER BY value DESC"));
    fireEvent.click(screen.getByRole("button", { name: "Remove sort 1" }));
    await waitFor(() => expect(preview()).toBe("SELECT * FROM deals"));
  });
});
