"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/errors";
import { usePortalLogin } from "@/lib/portal/hooks";

/** Portal login (separate realm). Authenticates a PortalUser against the workspace in the URL. */
export default function PortalLoginPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const router = useRouter();
  const login = usePortalLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const valid = /.+@.+\..+/.test(email) && password.length > 0;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setError("");
    try {
      await login.mutateAsync({ slug, email: email.trim(), password });
      router.push(`/portal/${slug}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Invalid credentials.");
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Portal sign in</h1>
        <p className="text-sm text-muted-foreground">Sign in to the {slug} portal.</p>
      </div>
      <form className="space-y-4" onSubmit={submit}>
        <div className="space-y-1.5">
          <Label htmlFor="p-email">Email</Label>
          <Input id="p-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-pass">Password</Label>
          <Input id="p-pass" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={!valid || login.isPending}>
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}
