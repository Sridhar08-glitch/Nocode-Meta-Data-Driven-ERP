"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { isValidSlug, slugify } from "@/lib/metadata/slug";
import { useCreateInbound, useDeleteInbound, useInboundWebhooks, useRotateInbound } from "@/lib/integrations/hooks";

/** Inbound Webhooks (Phase F3.5): public endpoints; the token+URL are shown ONCE on create/rotate. */
export function InboundWebhooks() {
  const inbound = useInboundWebhooks();
  const create = useCreateInbound();
  const del = useDeleteInbound();
  const rotate = useRotateInbound();
  const [creating, setCreating] = useState(false);
  const [reveal, setReveal] = useState<{ token: string; url: string } | null>(null);
  const [name, setName] = useState("");

  const rows = inbound.data?.results ?? [];
  const slug = slugify(name);
  const valid = !!name.trim() && isValidSlug(slug);

  async function submit() {
    if (!valid) return;
    try {
      const res = await create.mutateAsync({ name: name.trim(), slug });
      setReveal({ token: res.token, url: res.url });
      setCreating(false);
      setName("");
      toast.success("Inbound webhook created");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create");
    }
  }
  async function doRotate(id: string) {
    try {
      const res = await rotate.mutateAsync(id);
      setReveal(res);
      toast.success("Token rotated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not rotate token");
    }
  }
  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Inbound webhook removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove");
    }
  }

  return (
    <section className="space-y-4 border-t pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">Inbound webhooks</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New inbound
        </Button>
      </div>

      {inbound.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : inbound.isError ? (
        <ErrorState title="Couldn't load inbound webhooks" />
      ) : rows.length === 0 ? (
        <EmptyState title="No inbound webhooks" description="Receive external events at a tokenized public URL." className="border-0 p-0 text-left" />
      ) : (
        <ul className="space-y-2">
          {rows.map((w) => (
            <li key={w.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{w.name}</span>
                <code className="text-xs text-muted-foreground">{w.slug}</code>
                {w.is_active ? <Badge>active</Badge> : <Badge variant="secondary">inactive</Badge>}
                <span className="text-xs text-muted-foreground">{w.call_count} call(s)</span>
              </span>
              <span className="flex shrink-0 items-center gap-1">
                <Button variant="ghost" size="sm" aria-label={`Rotate token ${w.name}`} onClick={() => doRotate(w.id)} disabled={rotate.isPending}>
                  Rotate token
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Remove ${w.name}`} onClick={() => remove(w.id)} disabled={del.isPending}>
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New inbound webhook</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="ib-name">Name</Label>
              <Input id="ib-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ib-slug">Slug</Label>
              <Input id="ib-slug" value={slug} readOnly disabled className="font-mono text-xs" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={!valid || create.isPending}>
              {create.isPending ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!reveal} onOpenChange={(o) => !o && setReveal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Webhook token (shown once)</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">Copy this now — it can&apos;t be retrieved again.</p>
            <code aria-label="Inbound token" className="block break-all rounded bg-muted px-2 py-1 text-xs">{reveal?.token}</code>
            <p className="text-xs text-muted-foreground">POST events to:</p>
            <code className="block break-all rounded bg-muted px-2 py-1 text-xs">{reveal?.url}</code>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setReveal(null)}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
