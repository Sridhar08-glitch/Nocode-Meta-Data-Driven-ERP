"use client";

import { DependencyConsole } from "@/components/dependency/dependency-console";
import { useTenant } from "@/lib/tenant/context";

/**
 * Dependency & Impact Analysis (Phase P2.14) — change-safety console. Member-readable;
 * promotion precheck + executive summary are admin-only (the API also gates them).
 */
export default function AdminDependenciesPage() {
  const { workspace } = useTenant();
  const role = workspace?.role;
  const isAdmin = role === "owner" || role === "admin";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dependencies &amp; impact</h1>
        <p className="text-sm text-muted-foreground">
          See what depends on any object, preview the impact of a change, and check whether a delete
          or promotion is safe.
        </p>
      </div>
      <DependencyConsole isAdmin={isAdmin} />
    </div>
  );
}
