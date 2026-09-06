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
import { Switch } from "@/components/ui/switch";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import {
  type FeatureFlag,
  type FlagScope,
  type OverrideTarget,
  FLAG_SCOPES,
  OVERRIDE_TARGETS,
} from "@/lib/feature-flags/api";
import {
  useCreateFlag,
  useCreateOverride,
  useDeleteFlag,
  useDeleteOverride,
  useFeatureFlags,
  useFlagOverrides,
  useUpdateFlag,
} from "@/lib/feature-flags/hooks";
import { isValidSlug, slugify } from "@/lib/metadata/slug";

/** Feature Flag Management (Phase F2.9): master switch + %-rollout + scope + per-target overrides. */
export function FeatureFlagManager() {
  const flags = useFeatureFlags();
  const update = useUpdateFlag();
  const del = useDeleteFlag();
  const [creating, setCreating] = useState(false);
  const [overridesFor, setOverridesFor] = useState<FeatureFlag | null>(null);

  if (flags.isLoading) return <Skeleton className="h-64 w-full" />;
  if (flags.isError) return <ErrorState title="Couldn't load feature flags" />;
  const rows = flags.data ?? [];

  async function toggle(flag: FeatureFlag) {
    try {
      await update.mutateAsync({ id: flag.id, data: { enabled: !flag.enabled } });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update flag");
    }
  }
  async function remove(flag: FeatureFlag) {
    try {
      await del.mutateAsync(flag.id);
      toast.success("Flag removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove flag");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} flags</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New flag
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No feature flags"
          description="Gate modules and betas with a master switch, %-rollout, and per-role/user overrides."
          action={{ label: "New flag", onClick: () => setCreating(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((f) => (
            <li key={f.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <Switch checked={f.enabled} onCheckedChange={() => toggle(f)} aria-label={`Toggle ${f.key}`} disabled={update.isPending} />
                <code className="font-medium">{f.key}</code>
                {f.name && <span className="text-muted-foreground">{f.name}</span>}
                <Badge variant="outline">{f.scope}</Badge>
                {f.enabled && f.rollout_percent < 100 && <Badge variant="secondary">{f.rollout_percent}% rollout</Badge>}
                {!f.is_active && <Badge variant="secondary">inactive</Badge>}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                <Button variant="ghost" size="sm" aria-label={`Overrides for ${f.key}`} onClick={() => setOverridesFor(f)}>
                  Overrides
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Remove flag ${f.key}`} onClick={() => remove(f)} disabled={del.isPending}>
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {creating && <FlagDialog open onClose={() => setCreating(false)} />}
      {overridesFor && <OverridesDialog open flag={overridesFor} onClose={() => setOverridesFor(null)} />}
    </div>
  );
}

function FlagDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateFlag();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [scope, setScope] = useState<FlagScope>("workspace");
  const [enabled, setEnabled] = useState(false);
  const [rollout, setRollout] = useState(100);

  const key = slugify(name);
  const valid = !!name.trim() && isValidSlug(key) && rollout >= 0 && rollout <= 100;

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({ key, name: name.trim(), description: description.trim(), scope, enabled, rollout_percent: rollout });
      toast.success("Flag created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create flag");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New feature flag</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ff-name">Name</Label>
              <Input id="ff-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ff-key">Key</Label>
              <Input id="ff-key" value={key} readOnly disabled className="w-40 font-mono text-xs" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ff-scope">Scope</Label>
              <Select value={scope} onValueChange={(v) => setScope(v as FlagScope)}>
                <SelectTrigger id="ff-scope" className="w-36">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FLAG_SCOPES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="ff-desc">Description</Label>
            <Input id="ff-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={enabled} onCheckedChange={(v) => setEnabled(!!v)} /> Enabled (master switch)
            </label>
            <div className="space-y-1.5">
              <Label htmlFor="ff-rollout">Rollout %</Label>
              <Input id="ff-rollout" type="number" min={0} max={100} className="w-24" value={rollout} onChange={(e) => setRollout(Number(e.target.value))} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "Creating…" : "Create flag"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function OverridesDialog({ open, flag, onClose }: { open: boolean; flag: FeatureFlag; onClose: () => void }) {
  const overrides = useFlagOverrides(flag.id);
  const create = useCreateOverride();
  const del = useDeleteOverride();
  const [targetType, setTargetType] = useState<OverrideTarget>("workspace");
  const [targetId, setTargetId] = useState("");
  const [enabled, setEnabled] = useState(true);

  const needsTarget = targetType !== "workspace";
  const valid = !needsTarget || !!targetId.trim();

  async function add() {
    if (!valid) return;
    try {
      await create.mutateAsync({ flagId: flag.id, data: { target_type: targetType, target_id: needsTarget ? targetId.trim() : null, enabled } });
      toast.success("Override added");
      setTargetId("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add override");
    }
  }
  async function remove(overrideId: string) {
    try {
      await del.mutateAsync({ flagId: flag.id, overrideId });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove override");
    }
  }

  const rows = overrides.data ?? [];

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Overrides — {flag.key}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          {overrides.isLoading ? (
            <Skeleton className="h-16 w-full" />
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No overrides — the flag resolves from its master switch + rollout.</p>
          ) : (
            <ul className="space-y-1.5">
              {rows.map((o) => (
                <li key={o.id} className="flex items-center justify-between gap-2 rounded-md border p-2 text-sm">
                  <span className="flex items-center gap-2">
                    <Badge variant="outline">{o.target_type}</Badge>
                    {o.target_id && <code className="text-xs text-muted-foreground">{o.target_id}</code>}
                    <Badge variant={o.enabled ? "default" : "secondary"}>{o.enabled ? "on" : "off"}</Badge>
                  </span>
                  <Button variant="ghost" size="sm" aria-label={`Remove override ${o.id}`} onClick={() => remove(o.id)} disabled={del.isPending}>
                    ✕
                  </Button>
                </li>
              ))}
            </ul>
          )}

          <div className="flex flex-wrap items-end gap-2 border-t pt-3">
            <div className="space-y-1.5">
              <Label htmlFor="ov-target">Target</Label>
              <Select value={targetType} onValueChange={(v) => { setTargetType(v as OverrideTarget); setTargetId(""); }}>
                <SelectTrigger id="ov-target" className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {OVERRIDE_TARGETS.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {needsTarget && (
              <div className="space-y-1.5">
                <Label htmlFor="ov-id">{targetType === "role" ? "Role ID" : "User ID"}</Label>
                <Input id="ov-id" value={targetId} onChange={(e) => setTargetId(e.target.value)} className="w-56 font-mono text-xs" />
              </div>
            )}
            <label className="flex h-9 items-center gap-2 text-sm">
              <Checkbox checked={enabled} onCheckedChange={(v) => setEnabled(!!v)} /> on
            </label>
            <Button size="sm" onClick={add} disabled={!valid || create.isPending}>
              Add override
            </Button>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
