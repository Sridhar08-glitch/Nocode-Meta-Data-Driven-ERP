import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const dashQ = { isLoading: false, data: { breached: 3, warning: 2, on_track: 10, met: 7, paused: 1 } };
vi.mock("@/lib/sla/hooks", () => ({ useSlaDashboard: () => dashQ }));

import { SlaHealth } from "./sla-health";

describe("SlaHealth", () => {
  it("renders SLA status counts", () => {
    render(<SlaHealth />);
    expect(within(screen.getByLabelText("sla-breached")).getByText("3")).toBeInTheDocument();
    expect(within(screen.getByLabelText("sla-met")).getByText("7")).toBeInTheDocument();
  });
});
