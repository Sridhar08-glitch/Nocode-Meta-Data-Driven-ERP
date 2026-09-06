"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateWorkspace } from "@/lib/tenant/admin-hooks";
import { useTenant } from "@/lib/tenant/context";

/**
 * Self-service tenant creation (closes GAP-1). Rendered as the onboarding screen
 * when a signed-in user belongs to no workspace, and reusable from the switcher.
 */
export function CreateWorkspace({ onCreated }: { onCreated?: (slug: string) => void }) {
  const { switchWorkspace } = useTenant();
  const create = useCreateWorkspace();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const ws = await create.mutateAsync({ name: name.trim() });
      switchWorkspace(ws.slug);
      onCreated?.(ws.slug);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the workspace.");
    }
  }

  return (
    <form onSubmit={submit} className="w-full max-w-md space-y-4 rounded-lg border p-6">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold">Create your workspace</h2>
        <p className="text-sm text-muted-foreground">
          A workspace is your company&apos;s tenant. You&apos;ll be its owner and can install ERP
          modules and invite your team next.
        </p>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="ws-name">Workspace name</Label>
        <Input
          id="ws-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Acme Manufacturing"
          autoFocus
          required
        />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={!name.trim() || create.isPending} className="w-full">
        {create.isPending ? "Creating…" : "Create workspace"}
      </Button>
    </form>
  );
}
