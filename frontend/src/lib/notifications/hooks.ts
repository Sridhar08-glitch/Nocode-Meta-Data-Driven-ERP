"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { getAccessToken } from "@/lib/auth/token-store";
import { createReconnectingSocket, type SocketStatus } from "@/lib/realtime/socket";
import { useTenant } from "@/lib/tenant/context";

import {
  type NotificationListParams,
  type NotificationTemplateWrite,
  notificationsApi,
  preferencesApi,
  templatesApi,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => qc.invalidateQueries({ queryKey: ["notifications", ws] }),
  };
}

export function useNotifications(params: NotificationListParams = {}) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["notifications", ws, "list", params],
    queryFn: () => notificationsApi.list(params),
    enabled,
    staleTime: 15_000,
  });
}

export function useUnreadCount() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["notifications", ws, "unread-count"],
    queryFn: () => notificationsApi.unreadCount(),
    enabled,
    staleTime: 15_000,
  });
}

export function useMarkRead() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => notificationsApi.markRead(id), onSuccess: invalidate });
}

export function useMarkAllRead() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: () => notificationsApi.markAllRead(), onSuccess: invalidate });
}

/**
 * Live notifications: subscribes to `ws/notifications/` and refetches the inbox + unread count on
 * every push (the WS frame is a reduced view, so REST is the source of truth). Returns the socket
 * status for the bell's connection indicator. Reconnect/backoff/visibility live in the socket.
 */
export function useNotificationSocket(): SocketStatus {
  const { ws, enabled, invalidate } = useScope();
  const [status, setStatus] = useState<SocketStatus>("closed");

  useEffect(() => {
    if (!enabled) return;
    const sock = createReconnectingSocket({
      path: "ws/notifications/",
      getToken: getAccessToken,
      onMessage: () => invalidate(),
      onStatus: setStatus,
    });
    return () => sock.close();
    // re-open when the active workspace changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ws]);

  return status;
}

// ── templates + preferences (Phase F2.7) ─────────────────────────────────────────────
function useTplScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return { ws, enabled: isReady && !!ws, qc };
}

function unwrap<T>(d: T[] | { results: T[] } | undefined): T[] {
  if (!d) return [];
  return Array.isArray(d) ? d : d.results;
}

export function useTemplates() {
  const { ws, enabled } = useTplScope();
  return useQuery({
    queryKey: ["notification-templates", ws],
    queryFn: async () => unwrap(await templatesApi.list()),
    enabled,
    staleTime: 60_000,
  });
}
export function useCreateTemplate() {
  const { ws, qc } = useTplScope();
  return useMutation({
    mutationFn: (d: NotificationTemplateWrite) => templatesApi.create(d),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notification-templates", ws] }),
  });
}
export function useUpdateTemplate() {
  const { ws, qc } = useTplScope();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<NotificationTemplateWrite> }) => templatesApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notification-templates", ws] }),
  });
}
export function useDeleteTemplate() {
  const { ws, qc } = useTplScope();
  return useMutation({
    mutationFn: (id: string) => templatesApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notification-templates", ws] }),
  });
}
export function useTestTemplate() {
  return useMutation({ mutationFn: ({ id, context }: { id: string; context?: Record<string, unknown> }) => templatesApi.test(id, context) });
}

export function useNotificationPreferences() {
  const { ws, enabled } = useScope();
  return useQuery({ queryKey: ["notification-prefs", ws], queryFn: () => preferencesApi.list(), enabled, staleTime: 30_000 });
}
export function useSetPreference() {
  const { ws, qc } = useTplScope();
  return useMutation({
    mutationFn: ({ event_type, channel, enabled }: { event_type: string; channel: string; enabled: boolean }) =>
      preferencesApi.set(event_type, channel, enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notification-prefs", ws] }),
  });
}
