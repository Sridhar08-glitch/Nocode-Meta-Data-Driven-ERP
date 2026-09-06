import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api/request", () => ({
  apiGet: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
  apiSend: vi.fn(() => Promise.resolve({})),
}));

import { apiGet, apiSend } from "@/lib/api/request";

import { notificationsApi } from "./api";

beforeEach(() => {
  vi.mocked(apiGet).mockClear();
  vi.mocked(apiSend).mockClear();
});

describe("notificationsApi", () => {
  it("lists with no params and with filters", () => {
    notificationsApi.list();
    notificationsApi.list({ unread: true, channel: "in_app", date_from: "2026-01-01" });
    expect(apiGet).toHaveBeenCalledWith("/api/v1/notifications/");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/notifications/?unread=1&channel=in_app&date_from=2026-01-01",
    );
  });

  it("marks one read, marks all read, and fetches the unread count", () => {
    notificationsApi.markRead("n1");
    notificationsApi.markAllRead();
    notificationsApi.unreadCount();
    expect(apiSend).toHaveBeenCalledWith("/api/v1/notifications/n1/read/", "POST");
    expect(apiSend).toHaveBeenCalledWith("/api/v1/notifications/read-all/", "POST");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/notifications/unread-count/");
  });
});
