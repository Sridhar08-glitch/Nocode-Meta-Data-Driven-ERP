"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ErrorState } from "@/components/ui/states";
import { useUpdateWorkspace, useWorkspaceDetail } from "@/lib/tenant/admin-hooks";
import { useTenant } from "@/lib/tenant/context";

import { WorkspaceDangerZone } from "./workspace-danger-zone";

const PLANS = ["free", "starter", "pro", "enterprise"] as const;

/** Workspace identity + plan + limits (closes the workspace-settings part of GAP-8). */
export function WorkspaceSettings() {
  const { workspace } = useTenant();
  const isOwner = workspace?.role === "owner";
  const detail = useWorkspaceDetail();
  const update = useUpdateWorkspace();

  const [name, setName] = useState("");
  const [logo, setLogo] = useState("");
  const [plan, setPlan] = useState<(typeof PLANS)[number]>("free");
  const [maxMembers, setMaxMembers] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const d = detail.data;
    if (!d) return;
    setName(d.name);
    setLogo(d.logo_url || "");
    setPlan((PLANS.includes(d.plan as (typeof PLANS)[number]) ? d.plan : "free") as (typeof PLANS)[number]);
    setMaxMembers(String(d.max_members));
  }, [detail.data]);

  if (detail.isError)
    return <ErrorState title="Couldn't load workspace" action={{ label: "Retry", onClick: () => detail.refetch() }} />;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMsg(null);
    const payload: Record<string, unknown> = { name: name.trim(), logo_url: logo.trim(), plan };
    if (isOwner && maxMembers) payload.max_members = Number(maxMembers);
    try {
      await update.mutateAsync(payload);
      setMsg("Saved.");
      window.setTimeout(() => setMsg(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save.");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Workspace settings</h1>
        <p className="text-sm text-muted-foreground">Identity, plan, and limits for this tenant.</p>
      </div>

      <form onSubmit={save} className="max-w-lg space-y-4 rounded-lg border p-6">
        <div className="space-y-1.5">
          <Label htmlFor="ws-name">Name</Label>
          <Input id="ws-name" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ws-logo">Logo URL</Label>
          <Input id="ws-logo" value={logo} onChange={(e) => setLogo(e.target.value)} placeholder="https://…" />
        </div>
        <div className="space-y-1.5">
          <Label>Plan</Label>
          <Select value={plan} onValueChange={(v) => setPlan(v as (typeof PLANS)[number])}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              {PLANS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="ws-max">Max members {isOwner ? "" : "(owner only)"}</Label>
          <Input id="ws-max" type="number" min={1} value={maxMembers} disabled={!isOwner}
            onChange={(e) => setMaxMembers(e.target.value)} />
        </div>
        {msg && <p className="text-sm text-emerald-600">{msg}</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? "Saving…" : "Save changes"}
        </Button>
      </form>

      <WorkspaceDangerZone />
    </div>
  );
}
