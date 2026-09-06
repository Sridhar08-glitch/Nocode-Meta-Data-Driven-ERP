"use client";

import Link from "next/link";

import { HomeRuntime } from "@/components/studio/home-runtime";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/lib/auth/session";

function Welcome() {
  const user = useAuthStore((s) => s.user);
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold tracking-tight">
        Welcome{user?.full_name ? `, ${user.full_name}` : ""}
      </h1>
      <p className="text-muted-foreground">
        You&apos;re signed in. Publish a Studio application to scope this home to a curated layout.
      </p>
      <div className="flex gap-3">
        <Button asChild variant="outline">
          <Link href="/settings/sessions">Manage sessions</Link>
        </Button>
        <Button asChild variant="ghost">
          <Link href="/dev/components">Design system</Link>
        </Button>
      </div>
    </div>
  );
}

export default function HomePage() {
  return <HomeRuntime fallback={<Welcome />} />;
}
