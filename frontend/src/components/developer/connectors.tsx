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
import { CONNECTOR_AUTH_TYPES } from "@/lib/integrations/api";
import { useConnectors, useCreateConnector, useDeleteConnector, useTestConnector } from "@/lib/integrations/hooks";
import { isValidSlug, slugify } from "@/lib/metadata/slug";

/** HTTP Connectors (Phase F3.5): outbound API targets used by workflow http_request steps. */
export function Connectors() {
  const connectors = useConnectors();
  const create = useCreateConnector();
  const del = useDeleteConnector();
  const test = useTestConnector();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [authType, setAuthType] = useState<string>("none");

  const rows = connectors.data?.results ?? [];
  const slug = slugify(name);
  const valid = !!name.trim() && isValidSlug(slug) && /^https?:\/\//.test(baseUrl.trim());

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({ name: name.trim(), slug, base_url: baseUrl.trim(), auth_type: authType });
      toast.success("Connector created");
      setCreating(false);
      setName("");
      setBaseUrl("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create connector");
    }
  }
  async function runTest(id: string) {
    try {
      const res = await test.mutateAsync(id);
      toast.success(`Connector responded ${res.status ?? "?"}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Test failed");
    }
  }
  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Connector removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove connector");
    }
  }

  return (
    <section className="space-y-4 border-t pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">HTTP connectors</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New connector
        </Button>
      </div>

      {connectors.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : connectors.isError ? (
        <ErrorState title="Couldn't load connectors" />
      ) : rows.length === 0 ? (
        <EmptyState title="No connectors" description="Define reusable HTTP targets for workflows." className="border-0 p-0 text-left" />
      ) : (
        <ul className="space-y-2">
          {rows.map((c) => (
            <li key={c.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{c.name}</span>
                <Badge variant="outline">{c.auth_type}</Badge>
                <code className="text-xs text-muted-foreground">{c.base_url}</code>
              </span>
              <span className="flex shrink-0 items-center gap-1">
                <Button variant="ghost" size="sm" aria-label={`Test ${c.name}`} onClick={() => runTest(c.id)} disabled={test.isPending}>
                  Test
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Remove ${c.name}`} onClick={() => remove(c.id)} disabled={del.isPending}>
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
            <DialogTitle>New connector</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="cn-name">Name</Label>
              <Input id="cn-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cn-url">Base URL</Label>
              <Input id="cn-url" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.example.com" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cn-auth">Auth type</Label>
              <Select value={authType} onValueChange={setAuthType}>
                <SelectTrigger id="cn-auth" className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CONNECTOR_AUTH_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <p className="text-xs text-muted-foreground">Credentials are configured by secret reference after creation — never stored raw.</p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={!valid || create.isPending}>
              {create.isPending ? "Creating…" : "Create connector"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
