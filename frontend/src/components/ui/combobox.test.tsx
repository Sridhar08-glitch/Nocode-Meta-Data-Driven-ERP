import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { Combobox } from "./combobox";

function Harness() {
  const [value, setValue] = useState("");
  return (
    <Combobox
      aria-label="Timezone"
      value={value}
      onChange={setValue}
      options={[{ value: "UTC" }, { value: "Europe/Paris" }, { value: "America/New_York" }]}
    />
  );
}

describe("Combobox", () => {
  it("opens, filters, and selects an option", async () => {
    render(<Harness />);
    const trigger = screen.getByRole("combobox", { name: "Timezone" });
    expect(trigger).toHaveTextContent("Select…");

    fireEvent.click(trigger);
    fireEvent.change(await screen.findByLabelText("Timezone search"), { target: { value: "paris" } });

    // filtered to the single match
    expect(screen.getByRole("option", { name: "Europe/Paris" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "America/New_York" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("option", { name: "Europe/Paris" }));
    expect(trigger).toHaveTextContent("Europe/Paris");
  });
});
