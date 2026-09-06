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
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useEntities } from "@/lib/metadata/hooks";
import { isValidSlug, slugify } from "@/lib/metadata/slug";
import { useRoles } from "@/lib/permissions/hooks";
import type { Application } from "@/lib/studio/api";
import {
  useApplications,
  useCreateApp,
  useDeleteApp,
  useHomeLayouts,
  useNavigations,
  usePublishApp,
  useUpdateApp,
} from "@/lib/studio/hooks";

const NONE = "__none__";

/** Application Builder (Phase F2.8): define a packaged app surface; Draft→Publish via `is_published`. */
export function ApplicationBuilder() {
  const apps = useApplications();
  const del = useDeleteApp();
  const publish = usePublishApp();
  const [editing, setEditing] = useState<Application | null>(null);
  const [creating, setCreating] = useState(false);

  if (apps.isLoading) return <Skeleton className="h-64 w-full" />;
  if (apps.isError) return <ErrorState title="Couldn't load applications" />;
  const rows = apps.data?.results ?? [];

  async function remove(a: Application) {
    try {
      await del.mutateAsync(a.id);
      toast.success("Application removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove application");
    }
  }
  async function doPublish(a: Application) {
    try {
      await publish.mutateAsync(a.id);
      toast.success("Application published");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not publish");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} applications</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New application
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No applications"
          description="Package entities, navigation, and a home page into a switchable app."
          action={{ label: "New application", onClick: () => setCreating(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{a.name}</span>
                <code className="text-xs text-muted-foreground">{a.slug}</code>
                <Badge variant="outline">{a.included_entity_ids.length} entities</Badge>
                {a.is_published ? <Badge>published</Badge> : <Badge variant="secondary">draft</Badge>}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {!a.is_published && (
                  <Button variant="outline" size="sm" aria-label={`Publish ${a.name}`} onClick={() => doPublish(a)} disabled={publish.isPending}>
                    Publish
                  </Button>
                )}
                <Button variant="ghost" size="sm" aria-label={`Edit application ${a.name}`} onClick={() => setEditing(a)}>
                  Edit
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Remove application ${a.name}`} onClick={() => remove(a)} disabled={del.isPending}>
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {creating && <AppDialog open onClose={() => setCreating(false)} />}
      {editing && <AppDialog open application={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function AppDialog({ open, application, onClose }: { open: boolean; application?: Application; onClose: () => void }) {
  const isEdit = !!application;
  const entities = useEntities();
  const roles = useRoles();
  const navs = useNavigations();
  const homes = useHomeLayouts();
  const create = useCreateApp();
  const update = useUpdateApp();

  const [name, setName] = useState(application?.name ?? "");
  const [description, setDescription] = useState(application?.description ?? "");
  const [color, setColor] = useState(application?.color ?? "");
  const [entityIds, setEntityIds] = useState<string[]>(application?.included_entity_ids ?? []);
  const [roleIds, setRoleIds] = useState<string[]>(application?.role_ids ?? []);
  const [navId, setNavId] = useState<string>(application?.navigation_id ?? NONE);
  const [homeId, setHomeId] = useState<string>(application?.home_layout_id ?? NONE);

  const slug = isEdit ? application.slug : slugify(name);
  const valid = !!name.trim() && isValidSlug(slug) && entityIds.length > 0;
  const pending = create.isPending || update.isPending;

  const toggle = (set: typeof setEntityIds, id: string) =>
    set((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  async function submit() {
    if (!valid) return;
    const data = {
      name: name.trim(),
      description: description.trim(),
      color: color.trim(),
      included_entity_ids: entityIds,
      role_ids: roleIds,
      navigation_id: navId === NONE ? null : navId,
      home_layout_id: homeId === NONE ? null : homeId,
    };
    try {
      if (isEdit) {
        await update.mutateAsync({ id: application.id, data });
        toast.success("Application saved");
      } else {
        await create.mutateAsync({ slug, ...data });
        toast.success("Application created");
      }
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save application");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit application" : "New application"}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[65vh] space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="app-name">Name</Label>
              <Input id="app-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="app-color">Accent color</Label>
              <Input id="app-color" value={color} onChange={(e) => setColor(e.target.value)} placeholder="#2563eb" className="w-32" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="app-slug">Slug</Label>
              <Input id="app-slug" value={slug} readOnly disabled className="w-40 font-mono text-xs" />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="app-desc">Description</Label>
            <Textarea id="app-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>

          <div className="space-y-1.5">
            <Label>Entities ({entityIds.length})</Label>
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2">
              {(entities.data ?? []).map((e) => (
                <label key={e.id} className="flex items-center gap-2 text-sm">
                  <Checkbox checked={entityIds.includes(e.id)} onCheckedChange={() => toggle(setEntityIds, e.id)} aria-label={`Include ${e.name}`} />
                  {e.name}
                </label>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="app-nav">Navigation</Label>
              <Select value={navId} onValueChange={setNavId}>
                <SelectTrigger id="app-nav" className="w-52">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Default (metadata)</SelectItem>
                  {(navs.data?.results ?? []).map((n) => (
                    <SelectItem key={n.id} value={n.id}>
                      {n.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="app-home">Home layout</Label>
              <Select value={homeId} onValueChange={setHomeId}>
                <SelectTrigger id="app-home" className="w-52">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>None</SelectItem>
                  {(homes.data?.results ?? []).map((h) => (
                    <SelectItem key={h.id} value={h.id}>
                      {h.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Visible to roles (none = everyone)</Label>
            <div className="flex flex-wrap gap-2 rounded-md border p-2">
              {(roles.data ?? []).map((r) => (
                <label key={r.id} className="flex items-center gap-1.5 text-sm">
                  <Checkbox checked={roleIds.includes(r.id)} onCheckedChange={() => toggle(setRoleIds, r.id)} aria-label={`Role ${r.name}`} />
                  {r.name}
                </label>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || pending}>
            {pending ? "Saving…" : isEdit ? "Save application" : "Create application"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
