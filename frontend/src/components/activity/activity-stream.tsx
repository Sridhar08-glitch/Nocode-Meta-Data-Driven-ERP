"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { type ActivityEntry } from "@/lib/activity/api";
import { useActivityFeed } from "@/lib/activity/hooks";

function val(v: unknown): string {
  if (v === null || v === undefined || v === "") return "∅";
  return String(v);
}

/** Cross-entity, permission-scoped activity stream (Phase F2.5) with field-diff rendering. */
export function ActivityStream() {
  const [type, setType] = useState("");
  const [from, setFrom] = useState("");
  const feed = useActivityFeed({ activity_type: type || undefined, date_from: from || undefined, limit: 100 });
  const rows = feed.data?.results ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="act-type">Type</Label>
          <Input id="act-type" value={type} onChange={(e) => setType(e.target.value)} placeholder="field_changed" className="w-48" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="act-from">Since</Label>
          <Input id="act-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="w-44" />
        </div>
      </div>

      {feed.isLoading && <Skeleton className="h-64 w-full" />}
      {feed.isError && <ErrorState title="Couldn't load activity" />}
      {feed.data && rows.length === 0 && <EmptyState title="No activity" />}

      {rows.length > 0 && (
        <ul className="space-y-2">
          {rows.map((e) => (
            <li key={e.id} className="rounded-md border p-3 text-sm">
              <ActivityRow entry={e} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ActivityRow({ entry }: { entry: ActivityEntry }) {
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{entry.activity_type}</Badge>
        <span className="font-medium">{entry.actor_name || "System"}</span>
        <span className="text-muted-foreground">{entry.summary}</span>
        <span className="ml-auto text-xs text-muted-foreground">{new Date(entry.occurred_at).toLocaleString()}</span>
      </div>
      {entry.changes.length > 0 && (
        <ul className="ml-1 space-y-0.5 text-xs text-muted-foreground">
          {entry.changes.map((c, i) => (
            <li key={i}>
              <span className="font-medium text-foreground">{c.field_label || c.field_slug}</span>: {val(c.old)} → {val(c.new)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
