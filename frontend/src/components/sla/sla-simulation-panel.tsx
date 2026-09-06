"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { simulateDue, type SimulationResult } from "@/lib/sla/sla-simulation";
import { useBusinessHours } from "@/lib/sla/hooks";

/**
 * SLA simulation panel (Phase F2.7 hardening) — a CONFIG AID ONLY. It forward-walks a calendar's
 * business hours client-side to estimate a due datetime; the authoritative engine is the backend
 * `apps/sla/calculator.py`. Reuses the existing `useBusinessHours` hook + the pure `simulateDue`
 * utility (no duplicated SLA engine).
 */
export function SlaSimulationPanel() {
  const calendars = useBusinessHours();
  const rows = calendars.data?.results ?? [];

  const [calendarId, setCalendarId] = useState("");
  const [startISO, setStartISO] = useState("");
  const [hours, setHours] = useState("8");
  const [result, setResult] = useState<SimulationResult | null>(null);

  const calendar = rows.find((c) => c.id === calendarId);

  function run() {
    if (!calendar) {
      setResult({ error: "Pick a calendar." });
      return;
    }
    setResult(
      simulateDue({
        weekly_hours: calendar.weekly_hours ?? {},
        holidays: calendar.holidays ?? [],
        startISO,
        durationMinutes: Math.round(Number(hours) * 60),
      }),
    );
  }

  return (
    <section className="space-y-3 rounded-md border p-4" aria-label="SLA simulation">
      <div>
        <h2 className="text-sm font-semibold">Simulation preview</h2>
        <p className="text-xs text-muted-foreground">
          This tool is intended for calendar validation and planning. Actual SLA calculations are
          performed by the backend SLA engine.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="sim-calendar">Calendar</Label>
          <Select value={calendarId || undefined} onValueChange={setCalendarId}>
            <SelectTrigger id="sim-calendar" className="w-48">
              <SelectValue placeholder="Pick calendar" />
            </SelectTrigger>
            <SelectContent>
              {rows.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sim-start">Start</Label>
          <Input id="sim-start" type="datetime-local" className="w-52" value={startISO} onChange={(e) => setStartISO(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="sim-hours">SLA hours</Label>
          <Input id="sim-hours" type="number" min={0} step="0.5" className="w-24" value={hours} onChange={(e) => setHours(e.target.value)} />
        </div>
        <Button onClick={run}>Simulate</Button>
      </div>

      {result && (
        <div className="text-sm" role="status">
          {"error" in result ? (
            <span className="text-destructive">{result.error}</span>
          ) : (
            <span>
              Estimated due: <strong className="tabular-nums">{result.dueLabel}</strong>
            </span>
          )}
        </div>
      )}
    </section>
  );
}
