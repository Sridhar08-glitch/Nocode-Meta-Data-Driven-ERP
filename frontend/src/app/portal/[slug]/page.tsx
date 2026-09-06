"use client";

import { PortalShell } from "@/components/portal/portal-shell";
import { usePortalMe } from "@/lib/portal/hooks";

export default function PortalHomePage() {
  return (
    <PortalShell>
      <Home />
    </PortalShell>
  );
}

function Home() {
  const me = usePortalMe();
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold">Welcome{me.data?.full_name ? `, ${me.data.full_name}` : ""}</h1>
      <p className="text-sm text-muted-foreground">
        You&apos;re signed in to the portal. You can only see records linked to your account.
      </p>
    </div>
  );
}
