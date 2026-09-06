"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { usePortalLogout, usePortalMe } from "@/lib/portal/hooks";

/**
 * Portal shell + guard (Phase F3.7). Gates authenticated portal pages: if there's no portal session
 * it redirects to the portal login. Minimal branded chrome — deliberately NOT the member AppShell
 * (portal users are a separate realm and must never touch member context).
 */
export function PortalShell({ children }: { children: React.ReactNode }) {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const router = useRouter();
  const me = usePortalMe();
  const logout = usePortalLogout();

  const unauthenticated = me.isError || (!me.isLoading && !me.data);

  useEffect(() => {
    if (unauthenticated) router.replace(`/portal/${slug}/login`);
  }, [unauthenticated, router, slug]);

  if (me.isLoading || unauthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  async function doLogout() {
    await logout.mutateAsync();
    router.replace(`/portal/${slug}/login`);
  }

  return (
    <div className="min-h-screen">
      <header className="flex h-14 items-center justify-between border-b border-border px-4">
        <span className="font-semibold">{slug} portal</span>
        <span className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">{me.data?.email}</span>
          <Button variant="outline" size="sm" onClick={doLogout} disabled={logout.isPending}>
            Sign out
          </Button>
        </span>
      </header>
      <main className="mx-auto max-w-4xl p-6">{children}</main>
    </div>
  );
}
