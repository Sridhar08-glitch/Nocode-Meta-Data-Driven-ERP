"use client";

import { NotificationPreferences } from "@/components/notifications/notification-preferences";

export default function NotificationSettingsPage() {
  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Notification preferences</h1>
        <p className="text-sm text-muted-foreground">Choose which events notify you, and on which channels.</p>
      </div>
      <NotificationPreferences />
    </div>
  );
}
