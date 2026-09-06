"use client";

import { ReleaseConsole } from "@/components/environments/release-console";
import { useTenant } from "@/lib/tenant/context";

/**
 * Environment Promotion / Release Management (Phase P2.15) — release console.
 * Members can browse environments + packages; provisioning, the dashboard, package
 * creation, and the promotion lifecycle (approve/dry-run/promote/rollback) are admin-only
 * (the API also gates them).
 */
export default function AdminPromotionsPage() {
  const { workspace } = useTenant();
  const role = workspace?.role;
  const isAdmin = role === "owner" || role === "admin";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Environment promotions</h1>
        <p className="text-sm text-muted-foreground">
          Promote workspace configuration through DEV → TEST → UAT → PROD with risk-scored,
          separation-of-duties approvals, a merge commit, and a rollback point.
        </p>
      </div>
      <ReleaseConsole isAdmin={isAdmin} />
    </div>
  );
}
