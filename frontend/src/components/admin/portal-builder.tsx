"use client";

import { useEffect, useState } from "react";

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
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useEntities } from "@/lib/metadata/hooks";
import type { PortalConfig } from "@/lib/portal-admin/api";
import {
  useCreatePortalGrant,
  useCreatePortalUser,
  useDeletePortalGrant,
  useDeletePortalUser,
  usePortalConfig,
  usePortalGrants,
  usePortalUsers,
  useUpdatePortalConfig,
} from "@/lib/portal-admin/hooks";

/** Portal Builder (custom admin, Phase F3.7): define the portal, its users, and per-entity grants. */
export function PortalBuilder() {
  return (
    <div className="space-y-8">
      <ConfigSection />
      <UsersSection />
      <GrantsSection />
    </div>
  );
}

function ConfigSection() {
  const config = usePortalConfig();
  const update = useUpdatePortalConfig();
  const entities = useEntities();
  const [form, setForm] = useState<PortalConfig | null>(null);

  useEffect(() => {
    if (config.data) setForm(config.data);
  }, [config.data]);

  if (config.isLoading || !form) return <Skeleton className="h-40 w-full" />;
  if (config.isError) return <ErrorState title="Couldn't load portal config" />;

  const toggleEntity = (id: string) =>
    setForm((f) => (f ? { ...f, exposed_entity_ids: f.exposed_entity_ids.includes(id) ? f.exposed_entity_ids.filter((x) => x !== id) : [...f.exposed_entity_ids, id] } : f));

  async function save() {
    if (!form) return;
    try {
      await update.mutateAsync({
        is_enabled: form.is_enabled,
        name: form.name,
        primary_color: form.primary_color,
        welcome_message: form.welcome_message,
        exposed_entity_ids: form.exposed_entity_ids,
        allow_self_signup: form.allow_self_signup,
      });
      toast.success("Portal config saved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save config");
    }
  }

  return (
    <section className="space-y-4">
      <h2 className="text-sm font-medium text-muted-foreground">Portal configuration</h2>
      <label className="flex items-center gap-2 text-sm">
        <Switch checked={form.is_enabled} onCheckedChange={(v) => setForm((f) => (f ? { ...f, is_enabled: !!v } : f))} aria-label="Enable portal" />
        Portal enabled
      </label>
      <div className="flex flex-wrap gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="pc-name">Name</Label>
          <Input id="pc-name" value={form.name} onChange={(e) => setForm((f) => (f ? { ...f, name: e.target.value } : f))} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pc-color">Accent color</Label>
          <Input id="pc-color" value={form.primary_color} onChange={(e) => setForm((f) => (f ? { ...f, primary_color: e.target.value } : f))} placeholder="#2563eb" className="w-32" />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="pc-welcome">Welcome message</Label>
        <Textarea id="pc-welcome" rows={2} value={form.welcome_message} onChange={(e) => setForm((f) => (f ? { ...f, welcome_message: e.target.value } : f))} />
      </div>
      <div className="space-y-1.5">
        <Label>Exposed entities</Label>
        <div className="flex flex-wrap gap-2 rounded-md border p-2">
          {(entities.data ?? []).map((e) => (
            <label key={e.id} className="flex items-center gap-1.5 text-sm">
              <Checkbox checked={form.exposed_entity_ids.includes(e.id)} onCheckedChange={() => toggleEntity(e.id)} aria-label={`Expose ${e.name}`} />
              {e.name}
            </label>
          ))}
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={form.allow_self_signup} onCheckedChange={(v) => setForm((f) => (f ? { ...f, allow_self_signup: !!v } : f))} /> Allow self-signup
      </label>
      <Button onClick={save} disabled={update.isPending}>
        {update.isPending ? "Saving…" : "Save config"}
      </Button>
    </section>
  );
}

function UsersSection() {
  const users = usePortalUsers();
  const create = useCreatePortalUser();
  const del = useDeletePortalUser();
  const [adding, setAdding] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [portalType, setPortalType] = useState("customer");
  const [linkedRecord, setLinkedRecord] = useState("");

  const rows = users.data?.results ?? [];
  const valid = /.+@.+\..+/.test(email) && !!fullName.trim() && password.length >= 8;

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({
        email: email.trim(),
        full_name: fullName.trim(),
        password,
        portal_type: portalType.trim() || "customer",
        linked_record_id: linkedRecord.trim() || null,
      });
      toast.success("Portal user created");
      setAdding(false);
      setEmail("");
      setFullName("");
      setPassword("");
      setLinkedRecord("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create portal user");
    }
  }
  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Portal user removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove user");
    }
  }

  return (
    <section className="space-y-4 border-t pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">Portal users</h2>
        <Button size="sm" onClick={() => setAdding(true)}>
          New portal user
        </Button>
      </div>

      {users.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : users.isError ? (
        <ErrorState title="Couldn't load portal users" />
      ) : rows.length === 0 ? (
        <EmptyState title="No portal users" description="Provision external users who sign in to the portal realm." className="border-0 p-0 text-left" />
      ) : (
        <ul className="space-y-2">
          {rows.map((u) => (
            <li key={u.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{u.full_name}</span>
                <code className="text-xs text-muted-foreground">{u.email}</code>
                <Badge variant="outline">{u.portal_type}</Badge>
                {u.linked_record_id && <span className="text-xs text-muted-foreground">linked</span>}
                {!u.is_active && <Badge variant="secondary">inactive</Badge>}
              </span>
              <Button variant="ghost" size="sm" aria-label={`Remove ${u.email}`} onClick={() => remove(u.id)} disabled={del.isPending}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New portal user</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="pu-email">Email</Label>
                <Input id="pu-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pu-name">Full name</Label>
                <Input id="pu-name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="pu-pass">Password (min 8)</Label>
                <Input id="pu-pass" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pu-type">Portal type</Label>
                <Input id="pu-type" value={portalType} onChange={(e) => setPortalType(e.target.value)} className="w-36" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pu-linked">Linked record ID (row scope)</Label>
              <Input id="pu-linked" value={linkedRecord} onChange={(e) => setLinkedRecord(e.target.value)} placeholder="the record this user is scoped to" className="font-mono text-xs" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={!valid || create.isPending}>
              {create.isPending ? "Creating…" : "Create user"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function GrantsSection() {
  const grants = usePortalGrants();
  const entities = useEntities();
  const create = useCreatePortalGrant();
  const del = useDeletePortalGrant();
  const [adding, setAdding] = useState(false);
  const [entitySlug, setEntitySlug] = useState("");
  const [portalType, setPortalType] = useState("");
  const [linkField, setLinkField] = useState("");
  const [canRead, setCanRead] = useState(true);
  const [canCreate, setCanCreate] = useState(false);
  const [canUpdate, setCanUpdate] = useState(false);

  const rows = grants.data?.results ?? [];
  const valid = !!entitySlug && !!linkField.trim();

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({
        entity_slug: entitySlug,
        portal_type: portalType.trim(),
        link_field: linkField.trim(),
        can_read: canRead,
        can_create: canCreate,
        can_update: canUpdate,
      });
      toast.success("Grant created");
      setAdding(false);
      setLinkField("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create grant");
    }
  }
  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Grant removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove grant");
    }
  }

  return (
    <section className="space-y-4 border-t pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">Entity grants</h2>
        <Button size="sm" onClick={() => setAdding(true)}>
          New grant
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Each grant scopes an entity to portal users via a <code>link_field</code> that must equal the
        user&apos;s linked record — the server-enforced row isolation.
      </p>

      {grants.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : grants.isError ? (
        <ErrorState title="Couldn't load grants" />
      ) : rows.length === 0 ? (
        <EmptyState title="No grants" description="Grant portal users read/create/update on specific entities." className="border-0 p-0 text-left" />
      ) : (
        <ul className="space-y-2">
          {rows.map((g) => (
            <li key={g.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{g.entity_slug}</span>
                <Badge variant="outline">{g.portal_type || "all types"}</Badge>
                <code className="text-xs text-muted-foreground">link: {g.link_field}</code>
                <span className="text-xs text-muted-foreground">
                  {[g.can_read && "read", g.can_create && "create", g.can_update && "update"].filter(Boolean).join(" · ")}
                </span>
              </span>
              <Button variant="ghost" size="sm" aria-label={`Remove grant ${g.entity_slug}`} onClick={() => remove(g.id)} disabled={del.isPending}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}

      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New entity grant</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="pg-entity">Entity</Label>
                <Select value={entitySlug || undefined} onValueChange={setEntitySlug}>
                  <SelectTrigger id="pg-entity" className="w-44">
                    <SelectValue placeholder="Pick entity" />
                  </SelectTrigger>
                  <SelectContent>
                    {(entities.data ?? []).map((e) => (
                      <SelectItem key={e.id} value={e.slug}>
                        {e.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pg-type">Portal type (blank = all)</Label>
                <Input id="pg-type" value={portalType} onChange={(e) => setPortalType(e.target.value)} className="w-36" placeholder="customer" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pg-link">Link field</Label>
              <Input id="pg-link" value={linkField} onChange={(e) => setLinkField(e.target.value)} placeholder="field equal to the user's linked record" />
            </div>
            <div className="flex flex-wrap gap-4">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={canRead} onCheckedChange={(v) => setCanRead(!!v)} /> Read
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={canCreate} onCheckedChange={(v) => setCanCreate(!!v)} /> Create
              </label>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={canUpdate} onCheckedChange={(v) => setCanUpdate(!!v)} /> Update
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={!valid || create.isPending}>
              {create.isPending ? "Creating…" : "Create grant"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
