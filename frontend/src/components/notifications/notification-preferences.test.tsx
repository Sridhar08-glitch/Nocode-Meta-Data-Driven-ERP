import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NotificationPreference } from "@/lib/notifications/api";

const { toast } = vi.hoisted(() => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
vi.mock("@/components/ui/toast", () => ({ toast }));

const prefsQ = { isLoading: false, isError: false, data: { results: [] as NotificationPreference[], count: 0 } };
const setPref = { mutateAsync: vi.fn(() => Promise.resolve({})), isPending: false };
vi.mock("@/lib/notifications/hooks", () => ({
  useNotificationPreferences: () => prefsQ,
  useSetPreference: () => setPref,
}));

import { NotificationPreferences } from "./notification-preferences";

beforeEach(() => {
  prefsQ.data = { results: [], count: 0 };
  setPref.mutateAsync.mockClear().mockResolvedValue({});
  vi.clearAllMocks();
});

describe("NotificationPreferences", () => {
  it("defaults every event/channel to enabled when no row is stored", () => {
    render(<NotificationPreferences />);
    // "Assigned to me" via In-app — checkbox checked by default
    expect(screen.getByRole("checkbox", { name: "Assigned to me via In-app" })).toBeChecked();
  });

  it("reflects a stored disabled preference", () => {
    prefsQ.data = {
      results: [{ id: "p1", event_type: "record_assigned", channel: "email", enabled: false, created_at: "", updated_at: "" }],
      count: 1,
    };
    render(<NotificationPreferences />);
    expect(screen.getByRole("checkbox", { name: "Assigned to me via Email" })).not.toBeChecked();
  });

  it("toggling a cell upserts the preference with the new enabled value", async () => {
    render(<NotificationPreferences />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Mentioned in a comment via Email" }));
    await waitFor(() =>
      expect(setPref.mutateAsync).toHaveBeenCalledWith({ event_type: "comment_mention", channel: "email", enabled: false }),
    );
  });
});
