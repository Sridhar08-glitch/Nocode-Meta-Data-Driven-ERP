import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AuditEntry, AuditFilters } from "@/lib/audit/api";

const useAuditLog = vi.fn();
vi.mock("@/lib/audit/hooks", () => ({ useAuditLog: (f: AuditFilters) => useAuditLog(f) }));

import { AuditExplorer } from "./audit-explorer";

const entry = (over: Partial<AuditEntry> = {}): AuditEntry => ({
  id: "a1", actor_id: "u1", actor_type: "member", actor_name: "Ada", action: "updated",
  resource_type: "record", resource_id: "r1", changed_fields: ["status", "amount"],
  correlation_id: "", event_id: null, occurred_at: "2026-06-23T09:00:00Z", ...over,
});

function mockData(results: AuditEntry[], count: number) {
  useAuditLog.mockReturnValue({ isLoading: false, isError: false, data: { results, count } });
}

beforeEach(() => {
  useAuditLog.mockReset();
  mockData([entry()], 1);
});

describe("AuditExplorer", () => {
  it("renders entries and toggles changed fields", () => {
    render(<AuditExplorer />);
    expect(screen.getByText("by Ada")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Toggle changed fields for a1" }));
    expect(screen.getByText("status")).toBeInTheDocument();
    expect(screen.getByText("amount")).toBeInTheDocument();
  });

  it("applies filters and resets offset", () => {
    render(<AuditExplorer />);
    fireEvent.change(screen.getByLabelText("Resource type"), { target: { value: "workflow" } });
    fireEvent.change(screen.getByLabelText("Action"), { target: { value: "created" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    const last = useAuditLog.mock.calls.at(-1)![0] as AuditFilters;
    expect(last).toMatchObject({ resource_type: "workflow", action: "created", offset: 0 });
  });

  it("paginates with Next", () => {
    mockData([entry()], 120);
    render(<AuditExplorer />);
    expect(within(screen.getByLabelText("Audit range")).getByText(/1–50 of 120/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect((useAuditLog.mock.calls.at(-1)![0] as AuditFilters).offset).toBe(50);
  });
});
