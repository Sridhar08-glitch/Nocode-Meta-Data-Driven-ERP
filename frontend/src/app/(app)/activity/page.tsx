"use client";

import { ActivityStream } from "@/components/activity/activity-stream";

export default function ActivityPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Activity</h1>
        <p className="text-sm text-muted-foreground">A permission-scoped stream of everything happening across your workspace.</p>
      </div>
      <ActivityStream />
    </div>
  );
}
