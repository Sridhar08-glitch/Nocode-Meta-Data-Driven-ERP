"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { useRecordTimeline } from "@/lib/activity/hooks";

/**
 * Record Playback (Phase F2.5): a scrubber over the record's ordered event history. Each step
 * shows the event, who, when, and which fields changed; the cumulative panel shows the record's
 * fields as they were first touched up to that step. (The per-record timeline exposes changed
 * field NAMES, not historical values — full value time-travel would need the event-store payloads.)
 */
export function RecordPlayback({ entitySlug, recordId }: { entitySlug: string; recordId: string }) {
  const timeline = useRecordTimeline(entitySlug, recordId);
  const [step, setStep] = useState(0);

  if (timeline.isLoading) return <Skeleton className="h-40 w-full" />;
  if (timeline.isError) return <ErrorState title="Couldn't load history" />;
  const events = timeline.data?.events ?? [];
  if (events.length === 0) return <EmptyState title="No history" description="This record has no recorded events." />;

  const idx = Math.min(step, events.length - 1);
  const current = events[idx];
  const touched = new Set<string>();
  for (let i = 0; i <= idx; i++) for (const f of events[i].changed_fields) touched.add(f);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" aria-label="Previous step" disabled={idx === 0} onClick={() => setStep(idx - 1)}>
          ←
        </Button>
        <input
          type="range"
          aria-label="History step"
          min={0}
          max={events.length - 1}
          value={idx}
          onChange={(e) => setStep(Number(e.target.value))}
          className="flex-1"
        />
        <Button variant="outline" size="sm" aria-label="Next step" disabled={idx === events.length - 1} onClick={() => setStep(idx + 1)}>
          →
        </Button>
        <span className="text-xs text-muted-foreground">
          {idx + 1} / {events.length}
        </span>
      </div>

      <div className="rounded-md border p-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{current.event_type}</Badge>
          <span className="text-muted-foreground">v{current.version}</span>
          {current.actor_id && <span className="font-mono text-xs">{current.actor_id.slice(0, 8)}</span>}
          <span className="ml-auto text-xs text-muted-foreground">{new Date(current.occurred_at).toLocaleString()}</span>
        </div>
        {current.changed_fields.length > 0 && (
          <p className="mt-2 text-xs">
            Changed: {current.changed_fields.map((f) => (
              <Badge key={f} variant="secondary" className="mx-0.5">
                {f}
              </Badge>
            ))}
          </p>
        )}
      </div>

      <section aria-label="Fields touched so far">
        <h4 className="mb-1 text-xs font-medium text-muted-foreground">Fields touched through this step ({touched.size})</h4>
        {touched.size === 0 ? (
          <p className="text-xs text-muted-foreground">No field changes yet.</p>
        ) : (
          <div className="flex flex-wrap gap-1">
            {Array.from(touched).map((f) => (
              <Badge key={f} variant="outline">
                {f}
              </Badge>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
