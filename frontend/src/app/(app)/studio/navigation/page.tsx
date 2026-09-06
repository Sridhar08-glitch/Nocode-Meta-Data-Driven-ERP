"use client";

import { NavigationBuilder } from "@/components/studio/navigation-builder";

export default function NavigationPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Navigation</h1>
        <p className="text-sm text-muted-foreground">
          Custom permission-aware menu trees per workspace, application, or role.
        </p>
      </div>
      <NavigationBuilder />
    </div>
  );
}
