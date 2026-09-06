"use client";

import { ApplicationBuilder } from "@/components/studio/application-builder";

export default function ApplicationsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Applications</h1>
        <p className="text-sm text-muted-foreground">
          Package entities, navigation, and a home page into a switchable application.
        </p>
      </div>
      <ApplicationBuilder />
    </div>
  );
}
