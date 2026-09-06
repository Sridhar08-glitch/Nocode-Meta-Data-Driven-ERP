import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { findA11yViolations } from "@/test/a11y";

import { Badge } from "./badge";
import { Button } from "./button";
import { Checkbox } from "./checkbox";
import { Input } from "./input";
import { Label } from "./label";
import { RadioGroup, RadioGroupItem } from "./radio-group";
import { EmptyState } from "./states";
import { Stepper } from "./stepper";

describe("primitive accessibility (axe)", () => {
  it("Button has no violations", async () => {
    const { container } = render(<Button>Save</Button>);
    expect(await findA11yViolations(container)).toHaveLength(0);
  });

  it("Labelled input has no violations", async () => {
    const { container } = render(
      <div>
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" />
      </div>,
    );
    expect(await findA11yViolations(container)).toHaveLength(0);
  });

  it("Checkbox with label has no violations", async () => {
    const { container } = render(
      <label>
        <Checkbox /> Accept
      </label>,
    );
    expect(await findA11yViolations(container)).toHaveLength(0);
  });

  it("RadioGroup has no violations", async () => {
    const { container } = render(
      <RadioGroup defaultValue="a" aria-label="Choice">
        <RadioGroupItem value="a" aria-label="A" />
        <RadioGroupItem value="b" aria-label="B" />
      </RadioGroup>,
    );
    expect(await findA11yViolations(container)).toHaveLength(0);
  });

  it("Badge has no violations", async () => {
    const { container } = render(<Badge>New</Badge>);
    expect(await findA11yViolations(container)).toHaveLength(0);
  });

  it("EmptyState has no violations", async () => {
    const { container } = render(<EmptyState title="Nothing here" description="Add one." />);
    expect(await findA11yViolations(container)).toHaveLength(0);
  });

  it("Stepper exposes progress semantics with no violations", async () => {
    const { container } = render(
      <Stepper
        current={1}
        steps={[
          { id: "1", label: "One" },
          { id: "2", label: "Two" },
        ]}
      />,
    );
    expect(await findA11yViolations(container)).toHaveLength(0);
  });
});
