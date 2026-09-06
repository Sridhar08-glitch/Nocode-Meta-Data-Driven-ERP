import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SlaDashboard } from "@/lib/helpdesk/api";

const dashQ = { isLoading: false, isError: false, data: null as SlaDashboard | null };

vi.mock("@/lib/helpdesk/hooks", () => ({
  useSlaDashboard: () => dashQ,
}));

import { SlaPanel } from "./sla-panel";

beforeEach(() => {
  dashQ.data = null;
  dashQ.isLoading = false;
  dashQ.isError = false;
  vi.clearAllMocks();
});

describe("SlaPanel", () => {
  it("renders the SLA dashboard counts from query data", () => {
    dashQ.data = { breached: 3, warning: 5, on_track: 12, met: 40, paused: 2 };
    render(<SlaPanel />);
    expect(screen.getByText("Breached")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Warning")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("On track")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("Met")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("Paused")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows an error state when the dashboard fails to load", () => {
    dashQ.isError = true;
    render(<SlaPanel />);
    expect(screen.getByText("Couldn't load SLA dashboard")).toBeInTheDocument();
  });
});
