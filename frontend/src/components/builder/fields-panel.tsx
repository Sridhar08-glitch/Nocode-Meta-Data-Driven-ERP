"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "@/components/ui/toast";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { ApiError } from "@/lib/api/errors";
import { builderApi } from "@/lib/metadata/builder-api";
import { useDeleteField, useFields, usePromoteField } from "@/lib/metadata/builder-hooks";
import { FIELD_TYPE_LABELS } from "@/lib/metadata/slug";
import type { FieldDef } from "@/lib/metadata/types";

import { FieldDialog } from "./field-dialog";
import { ImpactWarningDialog } from "./impact-warning-dialog";

export function FieldsPanel({ entity }: { entity: string }) {
  const fields = useFields(entity);
  const del = useDeleteField(entity);
  const promote = usePromoteField(entity);
  const [editing, setEditing] = useState<FieldDef | null>(null);
  const [creating, setCreating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<FieldDef | null>(null);

  if (fields.isLoading) return <Skeleton className="h-64 w-full" />;
  if (fields.isError) return <ErrorState title="Couldn't load fields" />;

  const rows = fields.data ?? [];

  async function remove(f: FieldDef) {
    try {
      await del.mutateAsync(f.slug);
      toast.success(`Removed “${f.name}”`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove field");
    }
  }

  async function togglePromote(f: FieldDef) {
    try {
      await promote.mutateAsync({ fieldSlug: f.slug, promote: !f.is_promoted });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not change field");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} fields</h2>
        <Button size="sm" onClick={() => setCreating(true)}>
          Add field
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No fields yet"
          description="Add your first field to start capturing data."
          action={{ label: "Add field", onClick: () => setCreating(true) }}
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Label</TableHead>
              <TableHead>Slug</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Flags</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((f) => (
              <TableRow key={f.id}>
                <TableCell className="font-medium">{f.name}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">{f.slug}</TableCell>
                <TableCell>{FIELD_TYPE_LABELS[f.field_type] ?? f.field_type}</TableCell>
                <TableCell className="space-x-1">
                  {f.is_required && <Badge variant="secondary">required</Badge>}
                  {f.is_unique && <Badge variant="secondary">unique</Badge>}
                  {f.is_promoted ? (
                    <Badge>column</Badge>
                  ) : (
                    <Badge variant="outline">virtual</Badge>
                  )}
                </TableCell>
                <TableCell className="space-x-2 text-right">
                  {!f.is_system && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => togglePromote(f)}
                      disabled={promote.isPending}
                    >
                      {f.is_promoted ? "Demote" : "Promote"}
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => setEditing(f)}>
                    Edit
                  </Button>
                  {!f.is_system && (
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Delete ${f.name}`}
                      onClick={() => setConfirmDelete(f)}
                      disabled={del.isPending}
                    >
                      Delete
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {creating && (
        <FieldDialog entity={entity} open={creating} onOpenChange={setCreating} />
      )}
      {editing && (
        <FieldDialog
          entity={entity}
          field={editing}
          open={!!editing}
          onOpenChange={(o) => !o && setEditing(null)}
        />
      )}
      {confirmDelete && (
        <ImpactWarningDialog
          open
          title={`Delete field “${confirmDelete.name}”?`}
          queryKey={["impact", "field", entity, confirmDelete.slug]}
          fetcher={() => builderApi.fieldImpact(entity, confirmDelete.slug)}
          busy={del.isPending}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={async () => {
            await remove(confirmDelete);
            setConfirmDelete(null);
          }}
        />
      )}
    </div>
  );
}
