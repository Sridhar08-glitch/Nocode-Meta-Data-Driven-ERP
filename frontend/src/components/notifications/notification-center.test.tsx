import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Notification } from "@/lib/notifications/api";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const unread = { data: { count: 0 } };
const list = { isLoading: false, isError: false, data: { results: [] as Notification[], count: 0 } };
const markRead = { mutate: vi.fn(), isPending: false };
const markAll = { mutate: vi.fn(), isPending: false };
const socket = vi.fn();
vi.mock("@/lib/notifications/hooks", () => ({
  useNotificationSocket: () => socket(),
  useUnreadCount: () => unread,
  useNotifications: () => list,
  useMarkRead: () => markRead,
  useMarkAllRead: () => markAll,
}));

import { NotificationCenter } from "./notification-center";

function notif(over: Partial<Notification> = {}): Notification {
  return {
    id: "n1",
    template_id: null,
    recipient_id: "u1",
    recipient_type: "member",
    channel: "in_app",
    status: "sent",
    subject: "Deal won",
    body: "Acme closed",
    action_url: "/e/deals/d1",
    entity_id: null,
    record_id: null,
    group_key: "",
    actor_id: null,
    sent_at: null,
    read_at: null,
    failed_reason: "",
    created_at: "2026-01-01T00:00:00Z",
    ...over,
  };
}

beforeEach(() => {
  unread.data = { count: 0 };
  list.isLoading = false;
  list.isError = false;
  list.data = { results: [], count: 0 };
  markRead.isPending = false;
  markAll.isPending = false;
  vi.clearAllMocks();
});

describe("NotificationCenter", () => {
  it("subscribes to the realtime socket on mount", () => {
    render(<NotificationCenter />);
    expect(socket).toHaveBeenCalled();
  });

  it("shows no badge when there are no unread notifications", () => {
    render(<NotificationCenter />);
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
  });

  it("renders the unread count in the bell label and badge (capping at 99+)", () => {
    unread.data = { count: 150 };
    render(<NotificationCenter />);
    expect(screen.getByRole("button", { name: "Notifications (150 unread)" })).toBeInTheDocument();
    expect(screen.getByText("99+")).toBeInTheDocument();
  });

  it("opening an unread item marks it read and deep-links via action_url", () => {
    unread.data = { count: 1 };
    list.data = { results: [notif()], count: 1 };
    render(<NotificationCenter />);
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    fireEvent.click(screen.getByRole("button", { name: /Deal won/ }));
    expect(markRead.mutate).toHaveBeenCalledWith("n1");
    expect(push).toHaveBeenCalledWith("/e/deals/d1");
  });

  it("does not re-mark an already-read item and skips non-internal links", () => {
    unread.data = { count: 0 };
    list.data = { results: [notif({ read_at: "2026-01-02T00:00:00Z", action_url: "https://x.com" })], count: 1 };
    render(<NotificationCenter />);
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    fireEvent.click(screen.getByRole("button", { name: /Deal won/ }));
    expect(markRead.mutate).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("marks all read", () => {
    unread.data = { count: 2 };
    list.data = { results: [notif(), notif({ id: "n2" })], count: 2 };
    render(<NotificationCenter />);
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));
    expect(markAll.mutate).toHaveBeenCalled();
  });

  it("shows the empty state when the inbox is empty", () => {
    render(<NotificationCenter />);
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    expect(screen.getByText("You're all caught up")).toBeInTheDocument();
  });

  it("shows an error state when the inbox fails to load", () => {
    list.isError = true;
    render(<NotificationCenter />);
    fireEvent.click(screen.getByRole("button", { name: /Notifications/ }));
    expect(screen.getByText("Couldn't load notifications")).toBeInTheDocument();
  });
});
