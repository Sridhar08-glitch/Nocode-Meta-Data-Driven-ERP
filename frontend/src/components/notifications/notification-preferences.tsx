"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { PREFERENCE_CHANNELS, PREFERENCE_EVENT_TYPES } from "@/lib/notifications/api";
import { useNotificationPreferences, useSetPreference } from "@/lib/notifications/hooks";

/**
 * Per-user notification preferences (Phase F2.7 backfill): an event-type × channel matrix.
 * No stored row = enabled by default (matches the backend send-time default).
 */
export function NotificationPreferences() {
  const prefs = useNotificationPreferences();
  const setPref = useSetPreference();

  if (prefs.isLoading) return <Skeleton className="h-48 w-full" />;
  if (prefs.isError) return <ErrorState title="Couldn't load preferences" />;

  const map = new Map<string, boolean>();
  for (const p of prefs.data?.results ?? []) map.set(`${p.event_type}:${p.channel}`, p.enabled);
  const isOn = (event: string, channel: string) => map.get(`${event}:${channel}`) ?? true;

  async function toggle(event: string, channel: string, next: boolean) {
    try {
      await setPref.mutateAsync({ event_type: event, channel, enabled: next });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't save preference");
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b">
            <th className="px-3 py-2 text-left font-medium">Event</th>
            {PREFERENCE_CHANNELS.map((c) => (
              <th key={c.value} className="px-3 py-2 text-center font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {PREFERENCE_EVENT_TYPES.map((e) => (
            <tr key={e.value} className="border-b">
              <td className="px-3 py-2">{e.label}</td>
              {PREFERENCE_CHANNELS.map((c) => (
                <td key={c.value} className="px-3 py-2 text-center">
                  <Checkbox
                    aria-label={`${e.label} via ${c.label}`}
                    checked={isOn(e.value, c.value)}
                    onCheckedChange={(v) => toggle(e.value, c.value, !!v)}
                    disabled={setPref.isPending}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
