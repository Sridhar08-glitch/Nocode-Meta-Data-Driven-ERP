"use client";

import { FeatureFlagManager } from "@/components/feature-flags/feature-flag-manager";

export default function FeatureFlagsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Feature flags</h1>
        <p className="text-sm text-muted-foreground">
          Gate modules and betas with a master switch, percentage rollout, and per-role/user overrides.
        </p>
      </div>
      <FeatureFlagManager />
    </div>
  );
}
