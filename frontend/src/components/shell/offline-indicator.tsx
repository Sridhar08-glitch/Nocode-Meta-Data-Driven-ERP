"use client";

import { CloudOff, RefreshCw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useOnlineStatus, useOutboxAutoSync, useOutboxItems } from "@/lib/offline/hooks";
import { drainOutbox, outbox } from "@/lib/offline/store";

/**
 * Offline status + pending-sync indicator (Phase F3.8). Shows when offline or when the outbox has
 * queued mutations; opens a panel to sync, resolve conflicts (last-write-wins), and retry failures.
 * Hidden entirely when online with an empty outbox (no clutter).
 */
export function OfflineIndicator() {
  useOutboxAutoSync();
  const online = useOnlineStatus();
  const items = useOutboxItems();

  const pending = items.filter((i) => i.status === "pending").length;
  const conflicts = items.filter((i) => i.status === "conflict");
  const failed = items.filter((i) => i.status === "failed");

  if (online && items.length === 0) return null;

  const attention = conflicts.length + failed.length;

  return (
    <Popover>
      <PopoverTrigger
        aria-label="Sync status"
        className="relative flex items-center gap-1.5 rounded-md border border-input px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <CloudOff className={online ? "size-4 text-muted-foreground" : "size-4 text-amber-600"} />
        {!online && <span className="hidden sm:inline">Offline</span>}
        {items.length > 0 && (
          <Badge variant={attention > 0 ? "destructive" : "secondary"} className="h-4 px-1 text-[10px]">
            {items.length}
          </Badge>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium">{online ? "Pending sync" : "You're offline"}</span>
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1"
            aria-label="Sync now"
            disabled={!online || pending === 0}
            onClick={() => void drainOutbox()}
          >
            <RefreshCw className="size-3" /> Sync now
          </Button>
        </div>

        {items.length === 0 ? (
          <p className="text-xs text-muted-foreground">All changes are synced.</p>
        ) : (
          <ul className="max-h-72 space-y-1.5 overflow-y-auto">
            {items.map((i) => (
              <li key={i.id} className="rounded-md border p-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">{i.label}</span>
                  <Badge variant={i.status === "conflict" || i.status === "failed" ? "destructive" : "secondary"}>{i.status}</Badge>
                </div>
                {i.status === "conflict" && (
                  <div className="mt-1.5 flex gap-1.5">
                    <Button variant="outline" size="sm" className="h-6" aria-label={`Keep mine for ${i.label}`} onClick={() => outbox.resolveConflict(i.id, "local")}>
                      Keep mine
                    </Button>
                    <Button variant="outline" size="sm" className="h-6" aria-label={`Keep server for ${i.label}`} onClick={() => outbox.resolveConflict(i.id, "remote")}>
                      Keep server
                    </Button>
                  </div>
                )}
                {i.status === "failed" && (
                  <Button variant="outline" size="sm" className="mt-1.5 h-6" aria-label={`Retry ${i.label}`} onClick={() => outbox.retry(i.id)}>
                    Retry
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </PopoverContent>
    </Popover>
  );
}
