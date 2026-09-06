"use client";

import { PermissionBuilder } from "@/components/permissions/permission-builder";
import { PermissionDeniedState } from "@/components/ui/states";
import { useTenant } from "@/lib/tenant/context";

/** Permission Builder (Phase F1.9) — owner/admin only (the API gates writes regardless). */
export default function PermissionsPage() {
  const { workspace } = useTenant();
  const role = workspace?.role;
  const allowed = role === "owner" || role === "admin";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Permissions</h1>
        <p className="text-sm text-muted-foreground">
          Roles, RBAC grants, ABAC conditions, and field-level access &amp; masking.
        </p>
      </div>
      {allowed ? (
        <PermissionBuilder />
      ) : (
        <PermissionDeniedState description="Only workspace owners and admins can manage permissions." />
      )}
    </div>
  );
}
