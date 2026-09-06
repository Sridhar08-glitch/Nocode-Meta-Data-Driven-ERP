"use client";

import { useMemo, useState } from "react";

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
import { isValidSlug, slugify } from "@/lib/metadata/slug";
import {
  CARDINALITY_OPTIONS,
  ON_DELETE_OPTIONS,
  type Cardinality,
  type OnDelete,
  type RelationshipDef,
} from "@/lib/relationships/api";
import {
  useCreateRelationship,
  useDeleteRelationship,
  useRelationships,
} from "@/lib/relationships/hooks";

const CARDINALITY_GLYPH: Record<Cardinality, string> = {
  one_to_one: "1—1",
  one_to_many: "1—∞",
  many_to_many: "∞—∞",
  self_ref: "↻",
};

export function RelationshipsPanel({ entityId }: { entityId: string }) {
  const rels = useRelationships();
  const entities = useEntities();
  const del = useDeleteRelationship();
  const [creating, setCreating] = useState(false);

  const nameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of entities.data ?? []) m.set(e.id, e.name);
    return m;
  }, [entities.data]);

  if (rels.isLoading) return <Skeleton className="h-48 w-full" />;
  if (rels.isError) return <ErrorState title="Couldn't load relationships" />;

  // Show relationships touching this entity.
  const all = rels.data ?? [];
  const mine = all.filter(
    (r) => r.source_entity_id === entityId || r.target_entity_id === entityId,
  );

  async function remove(r: RelationshipDef) {
    try {
      await del.mutateAsync(r.id);
      toast.success("Relationship removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove relationship");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">
          {mine.length} relationship{mine.length === 1 ? "" : "s"}
        </h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          New relationship
        </Button>
      </div>

      {mine.length === 0 ? (
        <EmptyState
          title="No relationships"
          description="Link this entity to others (1:1, 1:N, N:N)."
          action={{ label: "New relationship", onClick: () => setCreating(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {mine.map((r) => (
            <li
              key={r.id}
              className="flex items-center justify-between rounded-md border p-3 text-sm"
            >
              <div className="flex items-center gap-3">
                <span className="font-medium">{nameById.get(r.source_entity_id) ?? "?"}</span>
                <span
                  className="font-mono text-muted-foreground"
                  aria-label={r.cardinality}
                  title={r.cardinality}
                >
                  {CARDINALITY_GLYPH[r.cardinality]}
                </span>
                <span className="font-medium">{nameById.get(r.target_entity_id) ?? "?"}</span>
                <span className="text-xs text-muted-foreground">({r.name})</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => remove(r)}
                disabled={del.isPending || r.is_system}
              >
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}

      {creating && (
        <RelationshipCreateDialog
          sourceEntityId={entityId}
          open={creating}
          onOpenChange={setCreating}
        />
      )}
    </div>
  );
}

function RelationshipCreateDialog({
  sourceEntityId,
  open,
  onOpenChange,
}: {
  sourceEntityId: string;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const entities = useEntities();
  const create = useCreateRelationship();
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [cardinality, setCardinality] = useState<Cardinality>("one_to_many");
  const [onDelete, setOnDelete] = useState<OnDelete>("detach");

  const slug = slugify(name);
  const valid = !!name.trim() && !!target && isValidSlug(slug);

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({
        name: name.trim(),
        slug,
        source_entity_id: sourceEntityId,
        target_entity_id: target,
        cardinality,
        on_delete: onDelete,
      });
      toast.success("Relationship created");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create relationship");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New relationship</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="rel-name">Name</Label>
            <Input id="rel-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rel-target">Target entity</Label>
            <Select value={target} onValueChange={setTarget}>
              <SelectTrigger id="rel-target">
                <SelectValue placeholder="Select an entity" />
              </SelectTrigger>
              <SelectContent>
                {(entities.data ?? []).map((e) => (
                  <SelectItem key={e.id} value={e.id}>
                    {e.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rel-cardinality">Cardinality</Label>
            <Select value={cardinality} onValueChange={(v) => setCardinality(v as Cardinality)}>
              <SelectTrigger id="rel-cardinality">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CARDINALITY_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="rel-ondelete">On delete</Label>
            <Select value={onDelete} onValueChange={(v) => setOnDelete(v as OnDelete)}>
              <SelectTrigger id="rel-ondelete">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ON_DELETE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "Creating…" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
