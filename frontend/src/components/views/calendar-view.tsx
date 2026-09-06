"use client";

import { useEffect, useState } from "react";

import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { calendarEvents, monthMatrix, reschedulePatch } from "@/lib/views/calendar";
import { applyMove } from "@/lib/views/kanban";
import { type Row } from "@/lib/views/types";
import { cn } from "@/lib/utils";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export interface CalendarViewProps {
  rows: Row[];
  dateField: string;
  titleField?: string;
  year: number;
  /** 0-based month. */
  month: number;
  /** Persist a reschedule; rejecting rolls back. */
  onReschedule: (id: string, patch: Record<string, string>) => Promise<unknown>;
}

/** Month calendar with optimistic reschedule + rollback (Phase F2.1). */
export function CalendarView({ rows, dateField, titleField, year, month, onReschedule }: CalendarViewProps) {
  const [local, setLocal] = useState<Row[]>(rows);
  useEffect(() => setLocal(rows), [rows]);

  const weeks = monthMatrix(year, month);
  const events = calendarEvents(local, dateField, titleField);
  const byDay: Record<string, typeof events> = {};
  for (const e of events) (byDay[e.day] ??= []).push(e);

  async function reschedule(id: string, newDay: string) {
    if (!newDay) return;
    const prev = local;
    setLocal((cur) => applyMove(cur, id, dateField, newDay)); // optimistic (reuses the field-patch helper)
    try {
      await onReschedule(id, reschedulePatch(dateField, newDay));
    } catch (err) {
      setLocal(prev); // rollback
      toast.error(err instanceof ApiError ? err.message : "Couldn't reschedule");
    }
  }

  return (
    <div className="overflow-x-auto">
      <div className="grid grid-cols-7 gap-px rounded-md border bg-border text-sm">
        {WEEKDAYS.map((d) => (
          <div key={d} className="bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
            {d}
          </div>
        ))}
        {weeks.flat().map((cell) => (
          <div
            key={cell.day}
            aria-label={cell.day}
            className={cn("min-h-20 bg-background p-1", !cell.inMonth && "opacity-50")}
          >
            <div className="text-xs text-muted-foreground">{cell.day.slice(8)}</div>
            <ul className="space-y-1">
              {(byDay[cell.day] ?? []).map((e) => (
                <li key={e.id} className="rounded bg-primary/10 px-1 py-0.5 text-xs">
                  <div className="truncate">{e.title}</div>
                  <input
                    type="date"
                    aria-label={`Reschedule ${e.title}`}
                    defaultValue={cell.day}
                    onChange={(ev) => reschedule(e.id, ev.target.value)}
                    className="mt-0.5 w-full bg-transparent text-[10px]"
                  />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
