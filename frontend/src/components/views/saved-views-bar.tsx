"use client";

import { Star } from "lucide-react";
import { useState } from "react";

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
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { SortClause } from "@/lib/nql/types";
import type { SavedView } from "@/lib/saved-views/api";
import {
  useCreateSavedView,
  useDeleteSavedView,
  useSavedViews,
  useUpdateSavedView,
} from "@/lib/saved-views/hooks";
import { cn } from "@/lib/utils";

export interface SavedViewsBarProps {
  entitySlug: string;
  /** Current sort, applied when saving a new view. */
  sort: SortClause | null;
  /** Apply a saved view's sort when loaded. */
  onApply: (sort: SortClause | null) => void;
}

/** Save / load / pin / delete per-member saved views for an entity list (Phase F1.9). */
export function SavedViewsBar({ entitySlug, sort, onApply }: SavedViewsBarProps) {
  const views = useSavedViews(entitySlug);
  const create = useCreateSavedView();
  const update = useUpdateSavedView();
  const del = useDeleteSavedView();
  const [saving, setSaving] = useState(false);
  const rows = views.data?.results ?? [];

  function load(v: SavedView) {
    onApply(v.sort_overrides[0] ?? null);
    toast.info(`Loaded “${v.name || "view"}”`);
  }

  async function togglePin(v: SavedView) {
    try {
      await update.mutateAsync({ id: v.id, data: { is_pinned: !v.is_pinned } });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update view");
    }
  }

  async function remove(v: SavedView) {
    try {
      await del.mutateAsync(v.id);
      toast.success("View deleted");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete view");
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {rows.map((v) => (
        <span
          key={v.id}
          className="inline-flex items-center gap-1 rounded-full border bg-muted/40 py-0.5 pl-2 pr-1 text-sm"
        >
          <button className="hover:underline" onClick={() => load(v)}>
            {v.name || "Untitled"}
          </button>
          <button
            aria-label={v.is_pinned ? `Unpin ${v.name}` : `Pin ${v.name}`}
            onClick={() => togglePin(v)}
            className="rounded p-0.5 hover:bg-muted"
          >
            <Star className={cn("size-3.5", v.is_pinned && "fill-current text-amber-500")} />
          </button>
          <button
            aria-label={`Delete ${v.name}`}
            onClick={() => remove(v)}
            className="rounded px-1 text-muted-foreground hover:bg-muted"
          >
            ✕
          </button>
        </span>
      ))}
      <Button variant="outline" size="sm" onClick={() => setSaving(true)}>
        Save view
      </Button>

      {saving && (
        <SaveViewDialog
          entitySlug={entitySlug}
          sort={sort}
          open={saving}
          onOpenChange={setSaving}
          onSaved={create}
        />
      )}
    </div>
  );
}

function SaveViewDialog({
  entitySlug,
  sort,
  open,
  onOpenChange,
  onSaved,
}: {
  entitySlug: string;
  sort: SortClause | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSaved: ReturnType<typeof useCreateSavedView>;
}) {
  const [name, setName] = useState("");

  async function submit() {
    if (!name.trim()) return;
    try {
      await onSaved.mutateAsync({
        entity_slug: entitySlug,
        name: name.trim(),
        sort_overrides: sort ? [sort] : [],
      });
      toast.success("View saved");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save view");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Save view</DialogTitle>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="view-name">Name</Label>
          <Input id="view-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!name.trim() || onSaved.isPending}>
            {onSaved.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
