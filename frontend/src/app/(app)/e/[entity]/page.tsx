"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { DataTable, type SortState } from "@/components/records/data-table";
import { SavedViewsBar } from "@/components/views/saved-views-bar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState, PermissionDeniedState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { useEntityMeta } from "@/lib/metadata/hooks";
import { buildListColumns } from "@/lib/records/columns";
import { useDeleteRecord, useRecords } from "@/lib/records/hooks";

const PAGE_SIZE = 25;

export default function EntityListPage({ params }: { params: { entity: string } }) {
  const slug = params.entity;
  const router = useRouter();
  const { entity, isLoading: metaLoading, isError: metaError } = useEntityMeta(slug);

  const [sort, setSort] = useState<SortState | null>(null);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const records = useRecords(slug, {
    sort: sort ? [sort] : undefined,
    limit: PAGE_SIZE,
    offset,
  });
  const del = useDeleteRecord(slug);

  const columns = useMemo(() => (entity ? buildListColumns(entity) : []), [entity]);
  const rows = records.data?.results ?? [];

  if (metaLoading) return <Skeleton className="h-64 w-full" />;
  if (metaError || !entity) {
    return <ErrorState title="Entity not found" description={`No entity “${slug}” in this workspace.`} />;
  }
  if (entity.can_read === false) {
    return <PermissionDeniedState description={`You can't view ${entity.plural_name}.`} />;
  }

  function toggleSort(field: string) {
    setSort((cur) =>
      cur?.field === field
        ? cur.direction === "asc"
          ? { field, direction: "desc" }
          : null
        : { field, direction: "asc" },
    );
  }

  function toggleRow(id: string) {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected((s) => (s.size === rows.length ? new Set() : new Set(rows.map((r) => String(r.id)))));
  }

  async function bulkDelete() {
    const ids = Array.from(selected);
    await Promise.all(ids.map((id) => del.mutateAsync(id).catch(() => null)));
    setSelected(new Set());
    toast.success(`Deleted ${ids.length} record${ids.length === 1 ? "" : "s"}`);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{entity.plural_name}</h1>
          <p className="text-sm text-muted-foreground">{records.data?.count ?? 0} records</p>
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <Button variant="outline" size="sm" onClick={bulkDelete} disabled={del.isPending}>
              <Trash2 className="size-4" /> Delete ({selected.size})
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={() => router.push(`/e/${slug}/views`)}>
            Views
          </Button>
          {entity.can_create !== false && (
            <Button size="sm" onClick={() => router.push(`/e/${slug}/new`)}>
              <Plus className="size-4" /> New
            </Button>
          )}
        </div>
      </div>

      <SavedViewsBar entitySlug={slug} sort={sort} onApply={(s) => setSort(s)} />

      {records.isLoading && <Skeleton className="h-64 w-full" />}
      {records.isError && (
        <ErrorState title="Couldn't load records" action={{ label: "Retry", onClick: () => records.refetch() }} />
      )}
      {records.data && rows.length === 0 && (
        <EmptyState
          title={`No ${entity.plural_name.toLowerCase()} yet`}
          description="Create your first record."
          action={
            entity.can_create !== false
              ? { label: "New record", onClick: () => router.push(`/e/${slug}/new`) }
              : undefined
          }
        />
      )}

      {records.data && rows.length > 0 && (
        <>
          <DataTable
            columns={columns}
            rows={rows}
            sort={sort}
            onSort={toggleSort}
            selected={selected}
            onToggleRow={toggleRow}
            onToggleAll={toggleAll}
            onRowClick={(id) => router.push(`/e/${slug}/${id}`)}
          />
          <div className="flex items-center justify-end gap-2 text-sm">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            >
              Previous
            </Button>
            <span className="text-muted-foreground">
              {offset + 1}–{offset + rows.length} of {records.data.count}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + rows.length >= records.data.count}
              onClick={() => setOffset((o) => o + PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
