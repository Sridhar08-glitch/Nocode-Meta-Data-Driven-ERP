"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useEntities } from "@/lib/metadata/hooks";
import { isValidSlug, slugify } from "@/lib/metadata/slug";
import { type SLATarget } from "@/lib/sla/api";
import { useCreatePolicy, useDeletePolicy, useSlaDashboard, useSlaPolicies } from "@/lib/sla/hooks";

const emptyTarget = (): SLATarget => ({ metric: "resolution", target_minutes: 480, warning_at_percent: 80, business_hours_only: false });

/** SLA config (Phase F2.4): dashboard counts + policy list + create with per-metric targets. */
export function SlaBuilder() {
  const dashboard = useSlaDashboard();
  const policies = useSlaPolicies();
  const del = useDeletePolicy();
  const [adding, setAdding] = useState(false);

  const d = dashboard.data;
  const rows = policies.data?.results ?? [];

  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Policy removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove policy");
    }
  }

  return (
    <div className="space-y-5">
      {d && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {(["breached", "warning", "on_track", "met", "paused"] as const).map((k) => (
            <div key={k} aria-label={k} className="rounded-md border p-3 text-center">
              <div className="text-2xl font-semibold tabular-nums">{d[k]}</div>
              <div className="text-xs text-muted-foreground">{k.replace("_", " ")}</div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} SLA policies</h2>
        <Button size="sm" onClick={() => setAdding(true)}>
          New policy
        </Button>
      </div>

      {policies.isLoading && <Skeleton className="h-40 w-full" />}
      {policies.isError && <ErrorState title="Couldn't load SLA policies" />}
      {policies.data && rows.length === 0 && (
        <EmptyState title="No SLA policies" description="Set response/resolution targets per entity." action={{ label: "New policy", onClick: () => setAdding(true) }} />
      )}
      {rows.length > 0 && (
        <ul className="space-y-2">
          {rows.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{p.name}</span>
                <Badge variant="outline">{p.targets.length} target(s)</Badge>
                {!p.is_active && <Badge variant="secondary">inactive</Badge>}
              </span>
              <Button variant="ghost" size="sm" aria-label={`Remove policy ${p.name}`} onClick={() => remove(p.id)} disabled={del.isPending}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}

      {adding && <PolicyDialog open onOpenChange={setAdding} />}
    </div>
  );
}

function PolicyDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const entities = useEntities();
  const create = useCreatePolicy();
  const [name, setName] = useState("");
  const [entityId, setEntityId] = useState("");
  const [appliesWhen, setAppliesWhen] = useState("");
  const [targets, setTargets] = useState<SLATarget[]>([emptyTarget()]);
  const slug = slugify(name);
  const valid = !!name.trim() && isValidSlug(slug) && !!entityId && targets.every((t) => t.metric.trim() && t.target_minutes > 0);

  const patch = (i: number, p: Partial<SLATarget>) => setTargets((ts) => ts.map((t, j) => (j === i ? { ...t, ...p } : t)));

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({ name: name.trim(), slug, entity_id: entityId, applies_when_nql: appliesWhen.trim(), targets });
      toast.success("Policy created");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create policy");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New SLA policy</DialogTitle>
        </DialogHeader>
        <div className="max-h-[60vh] space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="sla-name">Name</Label>
              <Input id="sla-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="sla-entity">Entity</Label>
              <Select value={entityId || undefined} onValueChange={setEntityId}>
                <SelectTrigger id="sla-entity" className="w-44">
                  <SelectValue placeholder="Pick entity" />
                </SelectTrigger>
                <SelectContent>
                  {(entities.data ?? []).map((e) => (
                    <SelectItem key={e.id} value={e.id}>
                      {e.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="sla-applies">Applies when (NQL — blank = all)</Label>
            <Input id="sla-applies" value={appliesWhen} onChange={(e) => setAppliesWhen(e.target.value)} placeholder="priority = 'high'" />
          </div>
          <div className="space-y-2">
            <Label>Targets</Label>
            {targets.map((t, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded-md border p-2">
                <Input aria-label={`Target ${i + 1} metric`} className="h-8 w-32" placeholder="metric" value={t.metric} onChange={(e) => patch(i, { metric: e.target.value })} />
                <Input aria-label={`Target ${i + 1} minutes`} type="number" className="h-8 w-28" value={t.target_minutes} onChange={(e) => patch(i, { target_minutes: Number(e.target.value) })} />
                <Input aria-label={`Target ${i + 1} warning percent`} type="number" className="h-8 w-24" value={t.warning_at_percent ?? 80} onChange={(e) => patch(i, { warning_at_percent: Number(e.target.value) })} />
                <label className="flex items-center gap-1 text-xs">
                  <Checkbox checked={!!t.business_hours_only} onCheckedChange={(v) => patch(i, { business_hours_only: !!v })} /> business hours
                </label>
                <Button variant="ghost" size="sm" aria-label={`Remove target ${i + 1}`} onClick={() => setTargets((ts) => ts.filter((_, j) => j !== i))}>
                  ✕
                </Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setTargets((ts) => [...ts, emptyTarget()])}>
              Add target
            </Button>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "Creating…" : "Create policy"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
