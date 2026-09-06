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
import type { WebhookSubscription } from "@/lib/integrations/api";
import {
  useCreateSub,
  useDeleteSub,
  useDeliveries,
  useSubscriptions,
  useTestSub,
  useToggleSub,
} from "@/lib/integrations/hooks";

/** Webhook Builder (Phase F3.5): outbound subscriptions — create, test, enable/disable, deliveries. */
export function WebhookBuilder() {
  const subs = useSubscriptions();
  const del = useDeleteSub();
  const test = useTestSub();
  const toggle = useToggleSub();
  const [creating, setCreating] = useState(false);
  const [logFor, setLogFor] = useState<WebhookSubscription | null>(null);

  const rows = subs.data?.results ?? [];

  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Webhook removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove webhook");
    }
  }
  async function runTest(id: string) {
    try {
      const res = await test.mutateAsync(id);
      toast.success(res.delivered ? `Test delivered (${res.delivery?.response_status ?? "?"})` : "Test queued");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Test failed");
    }
  }
  async function setEnabled(s: WebhookSubscription, enable: boolean) {
    try {
      await toggle.mutateAsync({ id: s.id, enable });
      toast.success(enable ? "Enabled" : "Disabled");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update");
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">Outgoing webhooks</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New webhook
        </Button>
      </div>

      {subs.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : subs.isError ? (
        <ErrorState title="Couldn't load webhooks" />
      ) : rows.length === 0 ? (
        <EmptyState title="No webhooks" description="Send signed HTTP POSTs when workspace events fire." action={{ label: "New webhook", onClick: () => setCreating(true) }} />
      ) : (
        <ul className="space-y-2">
          {rows.map((s) => {
            const disabled = s.status !== "active";
            return (
              <li key={s.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
                <span className="flex min-w-0 flex-wrap items-center gap-2">
                  <span className="font-medium">{s.name}</span>
                  <Badge variant={disabled ? "secondary" : "default"}>{s.status}</Badge>
                  <code className="truncate text-xs text-muted-foreground">{s.target_url}</code>
                  <span className="text-xs text-muted-foreground">{s.event_types.length} event(s) · ✓{s.success_count} ✗{s.failure_count}</span>
                </span>
                <span className="flex shrink-0 items-center gap-1">
                  <Button variant="ghost" size="sm" aria-label={`Test ${s.name}`} onClick={() => runTest(s.id)} disabled={test.isPending}>
                    Test
                  </Button>
                  <Button variant="ghost" size="sm" aria-label={`${disabled ? "Enable" : "Disable"} ${s.name}`} onClick={() => setEnabled(s, disabled)}>
                    {disabled ? "Enable" : "Disable"}
                  </Button>
                  <Button variant="ghost" size="sm" aria-label={`Deliveries ${s.name}`} onClick={() => setLogFor(s)}>
                    Log
                  </Button>
                  <Button variant="ghost" size="sm" aria-label={`Remove ${s.name}`} onClick={() => remove(s.id)} disabled={del.isPending}>
                    Delete
                  </Button>
                </span>
              </li>
            );
          })}
        </ul>
      )}

      {creating && <SubDialog onClose={() => setCreating(false)} />}
      {logFor && <DeliveriesDialog sub={logFor} onClose={() => setLogFor(null)} />}
    </section>
  );
}

function SubDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateSub();
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState("");
  const [secretRef, setSecretRef] = useState("");

  const eventList = events.split(",").map((s) => s.trim()).filter(Boolean);
  const valid = !!name.trim() && /^https?:\/\//.test(url.trim()) && eventList.length > 0;

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({ name: name.trim(), target_url: url.trim(), event_types: eventList, signing_secret_ref: secretRef.trim() || undefined });
      toast.success("Webhook created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create webhook");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New webhook</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="wh-name">Name</Label>
            <Input id="wh-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wh-url">Target URL</Label>
            <Input id="wh-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/hooks" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wh-events">Event types (comma-separated)</Label>
            <Input id="wh-events" value={events} onChange={(e) => setEvents(e.target.value)} placeholder="record.created, record.updated" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wh-secret">Signing secret reference (optional)</Label>
            <Input id="wh-secret" value={secretRef} onChange={(e) => setSecretRef(e.target.value)} placeholder="env var name — never the raw secret" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "Creating…" : "Create webhook"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeliveriesDialog({ sub, onClose }: { sub: WebhookSubscription; onClose: () => void }) {
  const deliveries = useDeliveries(sub.id);
  const rows = deliveries.data?.results ?? [];
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Deliveries — {sub.name}</DialogTitle>
        </DialogHeader>
        {deliveries.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No deliveries yet.</p>
        ) : (
          <ul className="max-h-80 space-y-1.5 overflow-y-auto">
            {rows.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-2 rounded-md border p-2 text-xs">
                <span className="flex items-center gap-2">
                  <Badge variant={d.status === "delivered" ? "default" : "secondary"}>{d.status}</Badge>
                  <span>{d.event_type}</span>
                  <span className="text-muted-foreground">#{d.attempt_number}</span>
                </span>
                <span className="text-muted-foreground">
                  {d.response_status ?? "—"} · {d.duration_ms}ms
                </span>
              </li>
            ))}
          </ul>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
