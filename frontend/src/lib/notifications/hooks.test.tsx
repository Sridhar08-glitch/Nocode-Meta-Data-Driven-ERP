import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", () => ({
  notificationsApi: {
    list: vi.fn(() => Promise.resolve({ results: [], count: 0 })),
    markRead: vi.fn(() => Promise.resolve({})),
    markAllRead: vi.fn(() => Promise.resolve({ updated: 3 })),
    unreadCount: vi.fn(() => Promise.resolve({ count: 2 })),
  },
}));
const { close, createReconnectingSocket } = vi.hoisted(() => {
  const closeFn = vi.fn();
  return { close: closeFn, createReconnectingSocket: vi.fn(() => ({ close: closeFn })) };
});
vi.mock("@/lib/realtime/socket", () => ({ createReconnectingSocket }));
vi.mock("@/lib/auth/token-store", () => ({ getAccessToken: () => "tok" }));

import { notificationsApi } from "./api";
import {
  useMarkAllRead,
  useMarkRead,
  useNotifications,
  useNotificationSocket,
  useUnreadCount,
} from "./hooks";

function wrap() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const Wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  Wrapper.displayName = "W";
  return { qc, wrapper: Wrapper };
}

beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  tenant.isReady = true;
  vi.clearAllMocks();
  createReconnectingSocket.mockReturnValue({ close });
});

describe("notification queries", () => {
  it("fetches the inbox (filtered) and the unread count", async () => {
    const { wrapper } = wrap();
    const list = renderHook(() => useNotifications({ unread: true }), { wrapper });
    const count = renderHook(() => useUnreadCount(), { wrapper });
    await waitFor(() => expect(list.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(count.result.current.isSuccess).toBe(true));
    expect(notificationsApi.list).toHaveBeenCalledWith({ unread: true });
    expect(count.result.current.data).toEqual({ count: 2 });
  });

  it("disables queries without a workspace", () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    const { result } = renderHook(() => useUnreadCount(), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
    expect(notificationsApi.unreadCount).not.toHaveBeenCalled();
  });
});

describe("mark-read mutations", () => {
  it("marks one read and invalidates the notifications root", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useMarkRead(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("n1");
    });
    expect(notificationsApi.markRead).toHaveBeenCalledWith("n1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["notifications", "acme"] });
  });

  it("marks all read", async () => {
    const { wrapper } = wrap();
    const { result } = renderHook(() => useMarkAllRead(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(notificationsApi.markAllRead).toHaveBeenCalled();
  });
});

describe("useNotificationSocket (realtime)", () => {
  it("opens the socket and refetches on every push", async () => {
    const { qc, wrapper } = wrap();
    const spy = vi.spyOn(qc, "invalidateQueries");
    renderHook(() => useNotificationSocket(), { wrapper });
    expect(createReconnectingSocket).toHaveBeenCalledTimes(1);
    const opts = (createReconnectingSocket.mock.calls[0] as unknown[])[0] as {
      path: string;
      onMessage: (d: unknown) => void;
    };
    expect(opts.path).toBe("ws/notifications/");
    // a server push triggers a refetch of the inbox. The push handler fires invalidateQueries,
    // whose refetch promise must settle INSIDE act() — otherwise it resolves in the next test and
    // leaves React's act machinery mid-flush, skipping that test's effects.
    await act(async () => {
      opts.onMessage({ id: "n9", subject: "Hi" });
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["notifications", "acme"] });
  });

  it("closes the socket on unmount", () => {
    const { wrapper } = wrap();
    const { unmount } = renderHook(() => useNotificationSocket(), { wrapper });
    expect(createReconnectingSocket).toHaveBeenCalledTimes(1);
    unmount();
    expect(close).toHaveBeenCalled();
  });

  it("does not open a socket without a workspace", () => {
    tenant.workspace = null;
    const { wrapper } = wrap();
    renderHook(() => useNotificationSocket(), { wrapper });
    expect(createReconnectingSocket).not.toHaveBeenCalled();
  });
});
