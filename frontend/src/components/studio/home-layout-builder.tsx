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
import { useRoles } from "@/lib/permissions/hooks";
import {
  type HomeLayout,
  type HomeWidget,
  type LayoutScope,
  HOME_WIDGET_TYPES,
  LAYOUT_SCOPES,
} from "@/lib/studio/api";
import {
  useApplications,
  useCreateHome,
  useDeleteHome,
  useHomeLayouts,
  usePublishHome,
  useUpdateHome,
} from "@/lib/studio/hooks";

const emptyWidget = (): HomeWidget => ({ type: "metric", title: "", width: 4 });

/** Home Layout Builder (Phase F2.8): widget-grid homes resolved per workspace/app/role/personal. */
export function HomeLayoutBuilder() {
  const layouts = useHomeLayouts();
  const del = useDeleteHome();
  const publish = usePublishHome();
  const [editing, setEditing] = useState<HomeLayout | null>(null);
  const [creating, setCreating] = useState(false);

  if (layouts.isLoading) return <Skeleton className="h-64 w-full" />;
  if (layouts.isError) return <ErrorState title="Couldn't load home layouts" />;
  const rows = layouts.data?.results ?? [];

  async function remove(l: HomeLayout) {
    try {
      await del.mutateAsync(l.id);
      toast.success("Layout removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove layout");
    }
  }
  async function doPublish(l: HomeLayout) {
    try {
      await publish.mutateAsync(l.id);
      toast.success("Layout published");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not publish");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} home layouts</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New layout
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No home layouts"
          description="Design widget-grid home pages per workspace, app, or role."
          action={{ label: "New layout", onClick: () => setCreating(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((l) => (
            <li key={l.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{l.name}</span>
                <Badge variant="outline">{l.scope}</Badge>
                <span className="text-xs text-muted-foreground">{l.widgets.length} widget(s)</span>
                {l.is_published ? <Badge>published</Badge> : <Badge variant="secondary">draft</Badge>}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {!l.is_published && (
                  <Button variant="outline" size="sm" aria-label={`Publish ${l.name}`} onClick={() => doPublish(l)} disabled={publish.isPending}>
                    Publish
                  </Button>
                )}
                <Button variant="ghost" size="sm" aria-label={`Edit layout ${l.name}`} onClick={() => setEditing(l)}>
                  Edit
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Remove layout ${l.name}`} onClick={() => remove(l)} disabled={del.isPending}>
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {creating && <LayoutDialog open onClose={() => setCreating(false)} />}
      {editing && <LayoutDialog open layout={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function LayoutDialog({ open, layout, onClose }: { open: boolean; layout?: HomeLayout; onClose: () => void }) {
  const isEdit = !!layout;
  const apps = useApplications();
  const roles = useRoles();
  const create = useCreateHome();
  const update = useUpdateHome();

  const [name, setName] = useState(layout?.name ?? "");
  const [scope, setScope] = useState<LayoutScope>(layout?.scope ?? "workspace");
  const [targetId, setTargetId] = useState<string>(layout?.target_id ?? "");
  const [widgets, setWidgets] = useState<HomeWidget[]>(layout?.widgets ?? [emptyWidget()]);

  const needsTarget = scope !== "workspace";
  const valid = !!name.trim() && (!needsTarget || !!targetId.trim());
  const pending = create.isPending || update.isPending;

  const patch = (i: number, p: Partial<HomeWidget>) => setWidgets((ws) => ws.map((w, j) => (j === i ? { ...w, ...p } : w)));

  async function submit() {
    if (!valid) return;
    const data = { name: name.trim(), scope, target_id: needsTarget ? targetId : null, widgets };
    try {
      if (isEdit) {
        await update.mutateAsync({ id: layout.id, data });
        toast.success("Layout saved");
      } else {
        await create.mutateAsync(data);
        toast.success("Layout created");
      }
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save layout");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit home layout" : "New home layout"}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[65vh] space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="hl-name">Name</Label>
              <Input id="hl-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="hl-scope">Scope</Label>
              <Select value={scope} onValueChange={(v) => { setScope(v as LayoutScope); setTargetId(""); }}>
                <SelectTrigger id="hl-scope" className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LAYOUT_SCOPES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {scope === "app" && (
            <div className="space-y-1.5">
              <Label htmlFor="hl-app">Application</Label>
              <Select value={targetId || undefined} onValueChange={setTargetId}>
                <SelectTrigger id="hl-app" className="w-52">
                  <SelectValue placeholder="Pick application" />
                </SelectTrigger>
                <SelectContent>
                  {(apps.data?.results ?? []).map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {scope === "role" && (
            <div className="space-y-1.5">
              <Label htmlFor="hl-role">Role</Label>
              <Select value={targetId || undefined} onValueChange={setTargetId}>
                <SelectTrigger id="hl-role" className="w-52">
                  <SelectValue placeholder="Pick role" />
                </SelectTrigger>
                <SelectContent>
                  {(roles.data ?? []).map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {scope === "personal" && (
            <div className="space-y-1.5">
              <Label htmlFor="hl-user">User ID</Label>
              <Input id="hl-user" value={targetId} onChange={(e) => setTargetId(e.target.value)} placeholder="member user id" className="w-72 font-mono text-xs" />
            </div>
          )}

          <div className="space-y-2">
            <Label>Widgets</Label>
            {widgets.map((w, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded-md border p-2">
                <Select value={w.type} onValueChange={(v) => patch(i, { type: v })}>
                  <SelectTrigger aria-label={`Widget ${i + 1} type`} className="h-8 w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {HOME_WIDGET_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input aria-label={`Widget ${i + 1} title`} className="h-8 w-44" placeholder="title" value={w.title ?? ""} onChange={(e) => patch(i, { title: e.target.value })} />
                <Input aria-label={`Widget ${i + 1} width`} type="number" min={1} max={12} className="h-8 w-20" value={w.width ?? 4} onChange={(e) => patch(i, { width: Number(e.target.value) })} />
                <span className="text-xs text-muted-foreground">/12</span>
                <Button variant="ghost" size="sm" aria-label={`Remove widget ${i + 1}`} onClick={() => setWidgets((ws) => ws.filter((_, j) => j !== i))}>
                  ✕
                </Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setWidgets((ws) => [...ws, emptyWidget()])}>
              Add widget
            </Button>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || pending}>
            {pending ? "Saving…" : isEdit ? "Save layout" : "Create layout"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
