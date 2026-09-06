import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { OutboxItem } from "@/lib/offline/outbox";

const { state, drainOutbox, outbox } = vi.hoisted(() => ({
  state: { online: true, items: [] as unknown[] },
  drainOutbox: vi.fn(),
  outbox: { resolveConflict: vi.fn(), retry: vi.fn() },
}));
vi.mock("@/lib/offline/hooks", () => ({
  useOnlineStatus: () => state.online,
  useOutboxItems: () => state.items,
  useOutboxAutoSync: () => {},
}));
vi.mock("@/lib/offline/store", () => ({ drainOutbox, outbox }));

import { OfflineIndicator } from "./offline-indicator";

const item = (over: Partial<OutboxItem> = {}): OutboxItem => ({
  id: "i1", method: "POST", path: "/x", label: "Create lead", status: "pending", attempts: 0, createdAt: 0, ...over,
});

beforeEach(() => {
  state.online = true;
  state.items = [];
  drainOutbox.mockClear();
  outbox.resolveConflict.mockClear();
  outbox.retry.mockClear();
});

describe("OfflineIndicator", () => {
  it("renders nothing when online with an empty outbox", () => {
    const { container } = render(<OfflineIndicator />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows Offline when disconnected", () => {
    state.online = false;
    render(<OfflineIndicator />);
    expect(screen.getByText("Offline")).toBeInTheDocument();
  });

  it("resolves a conflict (keep mine / keep server)", () => {
    state.items = [item({ status: "conflict", label: "Update lead" })];
    render(<OfflineIndicator />);
    fireEvent.click(screen.getByRole("button", { name: "Sync status" }));
    fireEvent.click(screen.getByRole("button", { name: "Keep mine for Update lead" }));
    expect(outbox.resolveConflict).toHaveBeenCalledWith("i1", "local");
    fireEvent.click(screen.getByRole("button", { name: "Keep server for Update lead" }));
    expect(outbox.resolveConflict).toHaveBeenCalledWith("i1", "remote");
  });

  it("retries a failed item", () => {
    state.items = [item({ status: "failed" })];
    render(<OfflineIndicator />);
    fireEvent.click(screen.getByRole("button", { name: "Sync status" }));
    fireEvent.click(screen.getByRole("button", { name: "Retry Create lead" }));
    expect(outbox.retry).toHaveBeenCalledWith("i1");
  });

  it("syncs now when online with pending items", () => {
    state.items = [item()];
    render(<OfflineIndicator />);
    fireEvent.click(screen.getByRole("button", { name: "Sync status" }));
    fireEvent.click(screen.getByRole("button", { name: "Sync now" }));
    expect(drainOutbox).toHaveBeenCalled();
  });
});
