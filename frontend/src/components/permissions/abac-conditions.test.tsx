import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import type { AbacCondition } from "@/lib/permissions/api";

import { AbacConditions } from "./abac-conditions";

function Harness({ initial = [] as AbacCondition[] }) {
  const [value, setValue] = useState<AbacCondition[]>(initial);
  return (
    <>
      <AbacConditions value={value} onChange={setValue} />
      <output data-testid="json">{JSON.stringify(value)}</output>
    </>
  );
}

const json = () => screen.getByTestId("json").textContent;

describe("AbacConditions", () => {
  it("adds a condition defaulting to $user.id", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Add condition" }));
    expect(json()).toBe(JSON.stringify([{ field: "", op: "=", value: "$user.id" }]));
  });

  it("edits the field and value", () => {
    render(<Harness initial={[{ field: "", op: "=", value: "$user.id" }]} />);
    fireEvent.change(screen.getByLabelText("Condition field 1"), { target: { value: "owner_id" } });
    fireEvent.change(screen.getByLabelText("Condition value 1"), { target: { value: "$me" } });
    expect(json()).toBe(JSON.stringify([{ field: "owner_id", op: "=", value: "$me" }]));
  });

  it("hides the value input for a nullary operator", async () => {
    render(<Harness initial={[{ field: "owner_id", op: "=", value: "x" }]} />);
    fireEvent.click(screen.getByRole("combobox", { name: "Condition operator 1" }));
    fireEvent.click(await screen.findByRole("option", { name: "is empty" }));
    expect(screen.queryByLabelText("Condition value 1")).not.toBeInTheDocument();
  });

  it("removes a condition", () => {
    render(<Harness initial={[{ field: "a", op: "=", value: "1" }]} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove condition 1" }));
    expect(json()).toBe("[]");
  });
});
