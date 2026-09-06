"use client";

import { HomeLayoutBuilder } from "@/components/studio/home-layout-builder";

export default function HomeLayoutsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Home layouts</h1>
        <p className="text-sm text-muted-foreground">
          Widget-grid home pages resolved per workspace, application, role, or person.
        </p>
      </div>
      <HomeLayoutBuilder />
    </div>
  );
}
