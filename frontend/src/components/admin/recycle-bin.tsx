"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { RecycleBinEntry } from "@/lib/recyclebin/api";
import {
  useBulkPurge,
  useBulkRestore,
  usePurgeEntry,
  useRecycleBin,
  useRestoreEntry,
} from "@/lib/recyclebin/hooks";

/** Days until auto-purge, floored at 0. */
function purgeCountdown(purgeAfter: string): number {
  const ms = new Date(purgeAfter).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / 86_400_000));
}

/** Recycle Bin admin (Phase F3.4): restore/purge soft-deleted records with a retention countdown. */
export function RecycleBin() {
  const [entitySlug, setEntitySlug] = useState("");
  const [includePurged, setIncludePurged] = useState(false);
  const query = useRecycleBin({ entity_slug: entitySlug.trim() || undefined, include_purged: includePurged });
  const restore = useRestoreEntry();
  const purge = usePurgeEntry();
  const bulkRestore = useBulkRestore();
  const bulkPurge = useBulkPurge();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmPurge, setConfirmPurge] = useState<RecycleBinEntry | "bulk" | null>(null);

  const rows = query.data?.results ?? [];
  const active = rows.filter((r) => !r.is_purged);

  function toggle(id: string) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function doRestore(id: string) {
    try {
      await restore.mutateAsync(id);
      toast.success("Record restored");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not restore");
    }
  }
  async function doPurge() {
    try {
      if (confirmPurge === "bulk") {
        await bulkPurge.mutateAsync(Array.from(selected));
        setSelected(new Set());
        toast.success("Records purged");
      } else if (confirmPurge) {
        await purge.mutateAsync(confirmPurge.id);
        toast.success("Record purged");
      }
      setConfirmPurge(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not purge");
    }
  }
  async function doBulkRestore() {
    try {
      await bulkRestore.mutateAsync(Array.from(selected));
      setSelected(new Set());
      toast.success("Records restored");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not restore");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Input aria-label="Filter by entity" placeholder="Filter by entity slug…" value={entitySlug} onChange={(e) => setEntitySlug(e.target.value)} className="h-9 w-56" />
        <label className="flex items-center gap-2 text-sm">
          <Checkbox checked={includePurged} onCheckedChange={(v) => setIncludePurged(!!v)} /> Include purged
        </label>
        {selected.size > 0 && (
          <span className="ml-auto flex items-center gap-2">
            <span className="text-sm text-muted-foreground">{selected.size} selected</span>
            <Button size="sm" variant="outline" onClick={doBulkRestore} disabled={bulkRestore.isPending}>
              Restore
            </Button>
            <Button size="sm" variant="outline" onClick={() => setConfirmPurge("bulk")}>
              Purge
            </Button>
          </span>
        )}
      </div>

      {query.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : query.isError ? (
        <ErrorState title="Couldn't load the recycle bin" />
      ) : rows.length === 0 ? (
        <EmptyState title="Recycle bin is empty" description="Deleted records appear here until they're restored or auto-purged." />
      ) : (
        <ul className="space-y-2">
          {rows.map((e) => (
            <li key={e.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex min-w-0 flex-wrap items-center gap-2">
                {!e.is_purged && (
                  <Checkbox checked={selected.has(e.id)} onCheckedChange={() => toggle(e.id)} aria-label={`Select ${e.record_title || e.record_id}`} />
                )}
                <span className="font-medium">{e.record_title || e.record_id}</span>
                <Badge variant="outline">{e.entity_slug}</Badge>
                {e.is_purged ? (
                  <Badge variant="secondary">purged</Badge>
                ) : (
                  <span className="text-xs text-muted-foreground">purges in {purgeCountdown(e.purge_after)}d</span>
                )}
              </span>
              {!e.is_purged && (
                <span className="flex shrink-0 items-center gap-1">
                  <Button variant="ghost" size="sm" aria-label={`Restore ${e.record_title || e.record_id}`} onClick={() => doRestore(e.id)} disabled={restore.isPending}>
                    Restore
                  </Button>
                  <Button variant="ghost" size="sm" aria-label={`Purge ${e.record_title || e.record_id}`} onClick={() => setConfirmPurge(e)}>
                    Purge
                  </Button>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <Dialog open={!!confirmPurge} onOpenChange={(o) => !o && setConfirmPurge(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Permanently delete?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Purging is irreversible — the record is hard-deleted from the database.
            {confirmPurge === "bulk" ? ` ${selected.size} record(s) will be purged.` : ""}
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmPurge(null)}>
              Cancel
            </Button>
            <Button onClick={doPurge} disabled={purge.isPending || bulkPurge.isPending}>
              Purge permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {active.length === 0 && rows.length > 0 && <p className="text-xs text-muted-foreground">All shown entries are already purged.</p>}
    </div>
  );
}
