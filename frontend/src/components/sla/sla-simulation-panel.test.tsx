import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { BusinessHours } from "@/lib/sla/api";

const bhQ = { data: { results: [] as BusinessHours[], count: 0 } };
vi.mock("@/lib/sla/hooks", () => ({ useBusinessHours: () => bhQ }));

import { SlaSimulationPanel } from "./sla-simulation-panel";

const cal: BusinessHours = {
  id: "c1",
  name: "EMEA",
  timezone: "Europe/Paris",
  schedule: {},
  weekly_hours: {
    mon: [{ start: "09:00", end: "17:00" }],
    tue: [{ start: "09:00", end: "17:00" }],
    wed: [{ start: "09:00", end: "17:00" }],
    thu: [{ start: "09:00", end: "17:00" }],
    fri: [{ start: "09:00", end: "17:00" }],
    sat: [],
    sun: [],
  },
  shifts: {},
  holidays: [],
  region: "EMEA",
  created_at: "",
  updated_at: "",
};

beforeEach(() => {
  bhQ.data = { results: [cal], count: 1 };
});

describe("SlaSimulationPanel", () => {
  it("renders the backend-authority warning", () => {
    render(<SlaSimulationPanel />);
    expect(screen.getByText(/Actual SLA calculations are performed by the backend SLA engine/)).toBeInTheDocument();
  });

  it("estimates a due datetime from calendar + start + hours", async () => {
    render(<SlaSimulationPanel />);
    fireEvent.click(screen.getByRole("combobox", { name: /Calendar/ }));
    fireEvent.click(await screen.findByRole("option", { name: "EMEA" }));
    fireEvent.change(screen.getByLabelText("Start"), { target: { value: "2026-06-29T09:00" } });
    fireEvent.change(screen.getByLabelText("SLA hours"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Simulate" }));
    await waitFor(() => expect(screen.getByText(/Estimated due:/)).toBeInTheDocument());
    expect(screen.getByText("2026-06-29 11:00")).toBeInTheDocument();
  });

  it("surfaces an error when no calendar is picked", () => {
    render(<SlaSimulationPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Simulate" }));
    expect(screen.getByText("Pick a calendar.")).toBeInTheDocument();
  });
});
