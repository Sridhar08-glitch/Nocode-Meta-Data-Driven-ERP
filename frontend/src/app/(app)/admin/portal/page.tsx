"use client";

import { PortalBuilder } from "@/components/admin/portal-builder";

export default function AdminPortalPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">External portal</h1>
        <p className="text-sm text-muted-foreground">
          Configure the customer/partner portal, provision portal users, and grant per-entity access.
        </p>
      </div>
      <PortalBuilder />
    </div>
  );
}
