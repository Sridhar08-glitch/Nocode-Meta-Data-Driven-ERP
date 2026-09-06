"use client";

import { Bell } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { Notification } from "@/lib/notifications/api";
import {
  useMarkAllRead,
  useMarkRead,
  useNotifications,
  useNotificationSocket,
  useUnreadCount,
} from "@/lib/notifications/hooks";
import { cn } from "@/lib/utils";

/** Live notification center (Phase F1.10): bell + unread badge + inbox over `ws/notifications/`. */
export function NotificationCenter() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  useNotificationSocket(); // live: refetches the queries below on every push
  const unread = useUnreadCount();
  const list = useNotifications();
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();

  const count = unread.data?.count ?? 0;
  const items = list.data?.results ?? [];

  function openItem(n: Notification) {
    if (!n.read_at) markRead.mutate(n.id);
    setOpen(false);
    if (n.action_url && n.action_url.startsWith("/")) router.push(n.action_url);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={count > 0 ? `Notifications (${count} unread)` : "Notifications"}
          className="relative"
        >
          <Bell className="size-4" />
          {count > 0 && (
            <span
              aria-hidden
              className="absolute -right-0.5 -top-0.5 flex min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-medium leading-4 text-primary-foreground"
            >
              {count > 99 ? "99+" : count}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <span className="text-sm font-medium">Notifications</span>
          {count > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={() => markAll.mutate()}
              disabled={markAll.isPending}
            >
              Mark all read
            </Button>
          )}
        </div>
        <div className="max-h-96 overflow-y-auto">
          {list.isLoading ? (
            <div className="space-y-2 p-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : list.isError ? (
            <ErrorState className="border-0" title="Couldn't load notifications" />
          ) : items.length === 0 ? (
            <EmptyState className="border-0" title="You're all caught up" />
          ) : (
            <ul>
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    onClick={() => openItem(n)}
                    className={cn(
                      "flex w-full gap-2 border-b border-border px-3 py-2 text-left text-sm last:border-0 hover:bg-muted",
                      !n.read_at && "bg-primary/5",
                    )}
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "mt-1.5 size-2 shrink-0 rounded-full",
                        n.read_at ? "bg-transparent" : "bg-primary",
                      )}
                    />
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{n.subject || "Notification"}</span>
                      {n.body && <span className="block truncate text-muted-foreground">{n.body}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
