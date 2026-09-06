"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import {
  type BusinessHours,
  type BusinessHoursWrite,
  type Holiday,
  type Interval,
  WEEKDAYS,
} from "@/lib/sla/api";
import { validateCalendar } from "@/lib/sla/calendar-validation";
import {
  useBusinessHours,
  useCreateBusinessHours,
  useUpdateBusinessHours,
} from "@/lib/sla/hooks";
import { IANA_TIMEZONES } from "@/lib/sla/timezones";

const DAY_LABELS: Record<string, string> = {
  mon: "Monday",
  tue: "Tuesday",
  wed: "Wednesday",
  thu: "Thursday",
  fri: "Friday",
  sat: "Saturday",
  sun: "Sunday",
};

type WeeklyHours = Record<string, Interval[]>;

const TZ_OPTIONS = IANA_TIMEZONES.map((t) => ({ value: t }));

function defaultWeekly(): WeeklyHours {
  const w: WeeklyHours = {};
  for (const d of WEEKDAYS) w[d] = d === "sat" || d === "sun" ? [] : [{ start: "09:00", end: "17:00" }];
  return w;
}

/**
 * Business Calendar Builder (Phase F2.7): manage `sla.BusinessHours` calendars — timezone, region,
 * per-day working intervals (`weekly_hours`, split shifts supported) and holidays. Reuses the F2.4
 * SLA hooks. There is no DELETE route for business-hours (backend), so calendars are create/edit only.
 */
export function BusinessCalendarBuilder() {
  const calendars = useBusinessHours();
  const [editing, setEditing] = useState<BusinessHours | null>(null);
  const [creating, setCreating] = useState(false);

  if (calendars.isLoading) return <Skeleton className="h-64 w-full" />;
  if (calendars.isError) return <ErrorState title="Couldn't load calendars" />;
  const rows = calendars.data?.results ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} calendars</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New calendar
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No business calendars"
          description="Define working hours and holidays for business-hours SLA targets."
          action={{ label: "New calendar", onClick: () => setCreating(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((c) => {
            const workingDays = WEEKDAYS.filter((d) => (c.weekly_hours?.[d]?.length ?? 0) > 0).length;
            return (
              <li key={c.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{c.name}</span>
                  <Badge variant="outline">{c.timezone || "UTC"}</Badge>
                  <span className="text-xs text-muted-foreground">
                    {workingDays} working day(s) · {c.holidays?.length ?? 0} holiday(s)
                  </span>
                </span>
                <Button variant="ghost" size="sm" aria-label={`Edit calendar ${c.name}`} onClick={() => setEditing(c)}>
                  Edit
                </Button>
              </li>
            );
          })}
        </ul>
      )}

      {creating && <CalendarDialog open onClose={() => setCreating(false)} />}
      {editing && <CalendarDialog open calendar={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function CalendarDialog({
  open,
  calendar,
  onClose,
}: {
  open: boolean;
  calendar?: BusinessHours;
  onClose: () => void;
}) {
  const isEdit = !!calendar;
  const create = useCreateBusinessHours();
  const update = useUpdateBusinessHours();

  const [name, setName] = useState(calendar?.name ?? "");
  const [timezone, setTimezone] = useState(calendar?.timezone ?? "UTC");
  const [region, setRegion] = useState(calendar?.region ?? "");
  const [weekly, setWeekly] = useState<WeeklyHours>(
    () => calendar?.weekly_hours && Object.keys(calendar.weekly_hours).length > 0
      ? WEEKDAYS.reduce((acc, d) => ({ ...acc, [d]: calendar.weekly_hours[d] ?? [] }), {} as WeeklyHours)
      : defaultWeekly(),
  );
  const [holidays, setHolidays] = useState<Holiday[]>(calendar?.holidays ?? []);

  const validation = validateCalendar({ name, timezone, weekly_hours: weekly, holidays });
  const valid = !validation.hasErrors;
  const pending = create.isPending || update.isPending;

  function patchInterval(day: string, i: number, p: Partial<Interval>) {
    setWeekly((w) => ({ ...w, [day]: w[day].map((iv, j) => (j === i ? { ...iv, ...p } : iv)) }));
  }
  function addInterval(day: string) {
    setWeekly((w) => ({ ...w, [day]: [...(w[day] ?? []), { start: "09:00", end: "17:00" }] }));
  }
  function removeInterval(day: string, i: number) {
    setWeekly((w) => ({ ...w, [day]: w[day].filter((_, j) => j !== i) }));
  }

  async function submit() {
    if (!valid) return;
    const data: BusinessHoursWrite = {
      name: name.trim(),
      timezone: timezone.trim(),
      region: region.trim(),
      weekly_hours: weekly,
      holidays: holidays.filter((h) => h.date.trim()),
    };
    try {
      if (isEdit) {
        await update.mutateAsync({ id: calendar.id, data });
        toast.success("Calendar saved");
      } else {
        await create.mutateAsync(data);
        toast.success("Calendar created");
      }
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save calendar");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit calendar" : "New business calendar"}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[65vh] space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="cal-name">Name</Label>
              <Input id="cal-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cal-tz">Timezone</Label>
              <Combobox
                id="cal-tz"
                aria-label="Timezone"
                value={timezone}
                onChange={setTimezone}
                options={TZ_OPTIONS}
                placeholder="Select timezone"
                searchPlaceholder="Search timezone…"
                triggerClassName="w-44"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cal-region">Region (optional)</Label>
              <Input id="cal-region" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="EMEA" className="w-32" />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Weekly hours (split shifts allowed)</Label>
            {WEEKDAYS.map((day) => (
              <div key={day} className="rounded-md border p-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{DAY_LABELS[day]}</span>
                  <Button type="button" variant="outline" size="sm" className="h-7" aria-label={`Add interval to ${DAY_LABELS[day]}`} onClick={() => addInterval(day)}>
                    Add shift
                  </Button>
                </div>
                {(weekly[day] ?? []).length === 0 ? (
                  <p className="mt-1 text-xs text-muted-foreground">Closed</p>
                ) : (
                  <div className="mt-2 space-y-1.5">
                    {weekly[day].map((iv, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <Input
                          type="time"
                          aria-label={`${DAY_LABELS[day]} shift ${i + 1} start`}
                          className="h-8 w-32"
                          value={iv.start}
                          onChange={(e) => patchInterval(day, i, { start: e.target.value })}
                        />
                        <span className="text-muted-foreground">–</span>
                        <Input
                          type="time"
                          aria-label={`${DAY_LABELS[day]} shift ${i + 1} end`}
                          className="h-8 w-32"
                          value={iv.end}
                          onChange={(e) => patchInterval(day, i, { end: e.target.value })}
                        />
                        <Button type="button" variant="ghost" size="sm" aria-label={`Remove ${DAY_LABELS[day]} shift ${i + 1}`} onClick={() => removeInterval(day, i)}>
                          ✕
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
                {validation.days[day]?.map((err) => (
                  <p key={err} role="alert" className="mt-1 text-xs text-destructive">
                    {err}
                  </p>
                ))}
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <Label>Holidays</Label>
            {validation.holidays.map((err) => (
              <p key={err} role="alert" className="text-xs text-destructive">
                {err}
              </p>
            ))}
            {holidays.map((h, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  type="date"
                  aria-label={`Holiday ${i + 1} date`}
                  className="h-8 w-40"
                  value={h.date}
                  onChange={(e) => setHolidays((hs) => hs.map((x, j) => (j === i ? { ...x, date: e.target.value } : x)))}
                />
                <Input
                  aria-label={`Holiday ${i + 1} name`}
                  className="h-8 w-44"
                  placeholder="name (optional)"
                  value={h.name ?? ""}
                  onChange={(e) => setHolidays((hs) => hs.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                />
                <Button type="button" variant="ghost" size="sm" aria-label={`Remove holiday ${i + 1}`} onClick={() => setHolidays((hs) => hs.filter((_, j) => j !== i))}>
                  ✕
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={() => setHolidays((hs) => [...hs, { date: "", name: "" }])}>
              Add holiday
            </Button>
          </div>

          {validation.general.length > 0 && (
            <ul role="alert" className="space-y-0.5 text-xs text-destructive">
              {validation.general.map((err) => (
                <li key={err}>{err}</li>
              ))}
            </ul>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || pending}>
            {pending ? "Saving…" : isEdit ? "Save calendar" : "Create calendar"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
