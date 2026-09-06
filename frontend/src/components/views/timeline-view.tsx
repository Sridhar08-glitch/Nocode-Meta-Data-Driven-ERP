"use client";

import { timelineEvents } from "@/lib/views/timeline";
import { type Row, type SortDir } from "@/lib/views/types";

export interface TimelineViewProps {
  rows: Row[];
  dateField: string;
  titleField?: string;
  dir?: SortDir;
}

/** Chronological event timeline (Phase F2.1). */
export function TimelineView({ rows, dateField, titleField, dir = "desc" }: TimelineViewProps) {
  const events = timelineEvents(rows, dateField, titleField, dir);
  if (events.length === 0) return <p className="text-sm text-muted-foreground">No dated records.</p>;

  return (
    <ol aria-label="Timeline" className="relative space-y-4 border-l pl-4">
      {events.map((e) => (
        <li key={e.id} className="relative">
          <span
            aria-hidden
            className="absolute -left-[21px] top-1 size-2 rounded-full bg-primary ring-2 ring-background"
          />
          <div className="text-xs text-muted-foreground">{e.at}</div>
          <div className="text-sm font-medium">{e.title}</div>
        </li>
      ))}
    </ol>
  );
}
