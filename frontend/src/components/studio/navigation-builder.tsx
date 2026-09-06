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
import { useEntities } from "@/lib/metadata/hooks";
import {
  type NavGroup,
  type Navigation,
  type NavItem,
  type NavItemType,
  type NavScope,
  NAV_ITEM_TYPES,
  NAV_SCOPES,
} from "@/lib/studio/api";
import {
  useCreateNav,
  useDeleteNav,
  useNavigations,
  usePublishNav,
  useUpdateNav,
} from "@/lib/studio/hooks";

const newItem = (): NavItem => ({ label: "", type: "entity", target: "" });
const newGroup = (): NavGroup => ({ label: "", items: [newItem()] });

function move<T>(arr: T[], i: number, dir: -1 | 1): T[] {
  const j = i + dir;
  if (j < 0 || j >= arr.length) return arr;
  const next = [...arr];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

/** Navigation Builder (Phase F2.8): permission-aware menu tree, reorder via ↑/↓ (no dnd dep). */
export function NavigationBuilder() {
  const navs = useNavigations();
  const del = useDeleteNav();
  const publish = usePublishNav();
  const [editing, setEditing] = useState<Navigation | null>(null);
  const [creating, setCreating] = useState(false);

  if (navs.isLoading) return <Skeleton className="h-64 w-full" />;
  if (navs.isError) return <ErrorState title="Couldn't load navigations" />;
  const rows = navs.data?.results ?? [];

  async function remove(n: Navigation) {
    try {
      await del.mutateAsync(n.id);
      toast.success("Navigation removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove navigation");
    }
  }
  async function doPublish(n: Navigation) {
    try {
      await publish.mutateAsync(n.id);
      toast.success("Navigation published");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not publish");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} menus</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New menu
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No custom menus"
          description="Build a menu tree; the shell falls back to metadata navigation when none is published."
          action={{ label: "New menu", onClick: () => setCreating(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((n) => (
            <li key={n.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{n.name}</span>
                <Badge variant="outline">{n.scope}</Badge>
                <span className="text-xs text-muted-foreground">{n.tree.length} group(s)</span>
                {n.is_published ? <Badge>published</Badge> : <Badge variant="secondary">draft</Badge>}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {!n.is_published && (
                  <Button variant="outline" size="sm" aria-label={`Publish ${n.name}`} onClick={() => doPublish(n)} disabled={publish.isPending}>
                    Publish
                  </Button>
                )}
                <Button variant="ghost" size="sm" aria-label={`Edit menu ${n.name}`} onClick={() => setEditing(n)}>
                  Edit
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Remove menu ${n.name}`} onClick={() => remove(n)} disabled={del.isPending}>
                  Delete
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {creating && <NavDialog open onClose={() => setCreating(false)} />}
      {editing && <NavDialog open navigation={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function NavDialog({ open, navigation, onClose }: { open: boolean; navigation?: Navigation; onClose: () => void }) {
  const isEdit = !!navigation;
  const entities = useEntities();
  const create = useCreateNav();
  const update = useUpdateNav();

  const [name, setName] = useState(navigation?.name ?? "");
  const [scope, setScope] = useState<NavScope>(navigation?.scope ?? "workspace");
  const [tree, setTree] = useState<NavGroup[]>(navigation?.tree ?? [newGroup()]);

  const valid = !!name.trim() && tree.length > 0 && tree.every((g) => g.label.trim() && g.items.every((it) => it.label.trim() && it.target.trim()));
  const pending = create.isPending || update.isPending;

  const patchGroup = (gi: number, p: Partial<NavGroup>) => setTree((t) => t.map((g, i) => (i === gi ? { ...g, ...p } : g)));
  const patchItem = (gi: number, ii: number, p: Partial<NavItem>) =>
    setTree((t) => t.map((g, i) => (i === gi ? { ...g, items: g.items.map((it, j) => (j === ii ? { ...it, ...p } : it)) } : g)));

  async function submit() {
    if (!valid) return;
    const data = { name: name.trim(), scope, tree };
    try {
      if (isEdit) {
        await update.mutateAsync({ id: navigation.id, data });
        toast.success("Navigation saved");
      } else {
        await create.mutateAsync(data);
        toast.success("Navigation created");
      }
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save navigation");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit menu" : "New menu"}</DialogTitle>
        </DialogHeader>
        <div className="max-h-[65vh] space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="nav-name">Name</Label>
              <Input id="nav-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="nav-scope">Scope</Label>
              <Select value={scope} onValueChange={(v) => setScope(v as NavScope)}>
                <SelectTrigger id="nav-scope" className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {NAV_SCOPES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-3">
            <Label>Menu groups</Label>
            {tree.map((g, gi) => (
              <div key={gi} className="space-y-2 rounded-md border p-2">
                <div className="flex items-center gap-2">
                  <Input aria-label={`Group ${gi + 1} label`} className="h-8 flex-1" placeholder="group label" value={g.label} onChange={(e) => patchGroup(gi, { label: e.target.value })} />
                  <Button variant="ghost" size="sm" aria-label={`Move group ${gi + 1} up`} disabled={gi === 0} onClick={() => setTree((t) => move(t, gi, -1))}>↑</Button>
                  <Button variant="ghost" size="sm" aria-label={`Move group ${gi + 1} down`} disabled={gi === tree.length - 1} onClick={() => setTree((t) => move(t, gi, 1))}>↓</Button>
                  <Button variant="ghost" size="sm" aria-label={`Remove group ${gi + 1}`} onClick={() => setTree((t) => t.filter((_, i) => i !== gi))}>✕</Button>
                </div>

                <div className="space-y-1.5 pl-3">
                  {g.items.map((it, ii) => (
                    <div key={ii} className="flex flex-wrap items-center gap-1.5">
                      <Input aria-label={`Group ${gi + 1} item ${ii + 1} label`} className="h-8 w-32" placeholder="label" value={it.label} onChange={(e) => patchItem(gi, ii, { label: e.target.value })} />
                      <Select value={it.type} onValueChange={(v) => patchItem(gi, ii, { type: v as NavItemType, target: "" })}>
                        <SelectTrigger aria-label={`Group ${gi + 1} item ${ii + 1} type`} className="h-8 w-32">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {NAV_ITEM_TYPES.map((t) => (
                            <SelectItem key={t.value} value={t.value}>
                              {t.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {it.type === "entity" ? (
                        <Select value={it.target || undefined} onValueChange={(v) => patchItem(gi, ii, { target: v })}>
                          <SelectTrigger aria-label={`Group ${gi + 1} item ${ii + 1} entity`} className="h-8 w-36">
                            <SelectValue placeholder="entity" />
                          </SelectTrigger>
                          <SelectContent>
                            {(entities.data ?? []).map((e) => (
                              <SelectItem key={e.id} value={e.slug}>
                                {e.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <Input
                          aria-label={`Group ${gi + 1} item ${ii + 1} target`}
                          className="h-8 w-40"
                          placeholder={it.type === "external" ? "https://…" : "/path"}
                          value={it.target}
                          onChange={(e) => patchItem(gi, ii, { target: e.target.value })}
                        />
                      )}
                      <Button variant="ghost" size="sm" aria-label={`Move group ${gi + 1} item ${ii + 1} up`} disabled={ii === 0} onClick={() => patchGroup(gi, { items: move(g.items, ii, -1) })}>↑</Button>
                      <Button variant="ghost" size="sm" aria-label={`Move group ${gi + 1} item ${ii + 1} down`} disabled={ii === g.items.length - 1} onClick={() => patchGroup(gi, { items: move(g.items, ii, 1) })}>↓</Button>
                      <Button variant="ghost" size="sm" aria-label={`Remove group ${gi + 1} item ${ii + 1}`} onClick={() => patchGroup(gi, { items: g.items.filter((_, j) => j !== ii) })}>✕</Button>
                    </div>
                  ))}
                  <Button variant="outline" size="sm" className="h-7" aria-label={`Add item to group ${gi + 1}`} onClick={() => patchGroup(gi, { items: [...g.items, newItem()] })}>
                    Add item
                  </Button>
                </div>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setTree((t) => [...t, newGroup()])}>
              Add group
            </Button>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || pending}>
            {pending ? "Saving…" : isEdit ? "Save menu" : "Create menu"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
