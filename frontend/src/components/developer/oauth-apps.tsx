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
import { useCreateOAuth, useDeleteOAuth, useOAuthApps } from "@/lib/integrations/hooks";

/** OAuth Apps (Phase F3.5): OAuth client registrations; the secret is stored by reference only. */
export function OAuthApps() {
  const apps = useOAuthApps();
  const create = useCreateOAuth();
  const del = useDeleteOAuth();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("");
  const [clientId, setClientId] = useState("");
  const [secretRef, setSecretRef] = useState("");
  const [scopes, setScopes] = useState("");
  const [redirect, setRedirect] = useState("");

  const rows = apps.data?.results ?? [];
  const valid = !!name.trim() && !!provider.trim() && !!clientId.trim();

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({
        name: name.trim(),
        provider: provider.trim(),
        client_id: clientId.trim(),
        client_secret_ref: secretRef.trim() || undefined,
        scopes: scopes.split(",").map((s) => s.trim()).filter(Boolean),
        redirect_uri: redirect.trim() || undefined,
      });
      toast.success("OAuth app created");
      setCreating(false);
      setName("");
      setProvider("");
      setClientId("");
      setSecretRef("");
      setScopes("");
      setRedirect("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create OAuth app");
    }
  }
  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("OAuth app removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove OAuth app");
    }
  }

  return (
    <section className="space-y-4 border-t pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">OAuth apps</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New OAuth app
        </Button>
      </div>

      {apps.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : apps.isError ? (
        <ErrorState title="Couldn't load OAuth apps" />
      ) : rows.length === 0 ? (
        <EmptyState title="No OAuth apps" description="Register OAuth client credentials for outbound integrations." className="border-0 p-0 text-left" />
      ) : (
        <ul className="space-y-2">
          {rows.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{a.name}</span>
                <Badge variant="outline">{a.provider}</Badge>
                <code className="text-xs text-muted-foreground">{a.client_id}</code>
                {a.scopes.length > 0 && <span className="text-xs text-muted-foreground">{a.scopes.length} scope(s)</span>}
              </span>
              <Button variant="ghost" size="sm" aria-label={`Remove ${a.name}`} onClick={() => remove(a.id)} disabled={del.isPending}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New OAuth app</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="oa-name">Name</Label>
                <Input id="oa-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="oa-provider">Provider</Label>
                <Input id="oa-provider" value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="google, github…" className="w-40" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="oa-client">Client ID</Label>
              <Input id="oa-client" value={clientId} onChange={(e) => setClientId(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="oa-secret">Client secret reference</Label>
              <Input id="oa-secret" value={secretRef} onChange={(e) => setSecretRef(e.target.value)} placeholder="env var name — never the raw secret" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="oa-scopes">Scopes (comma-separated)</Label>
              <Input id="oa-scopes" value={scopes} onChange={(e) => setScopes(e.target.value)} placeholder="openid, email" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="oa-redirect">Redirect URI</Label>
              <Input id="oa-redirect" value={redirect} onChange={(e) => setRedirect(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={!valid || create.isPending}>
              {create.isPending ? "Creating…" : "Create OAuth app"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
