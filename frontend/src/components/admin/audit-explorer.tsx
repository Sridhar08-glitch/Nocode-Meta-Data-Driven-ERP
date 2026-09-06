"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { AuditEntry } from "@/lib/audit/api";
import { useAuditLog } from "@/lib/audit/hooks";

const PAGE = 50;

/** Audit explorer (Phase F3.2): filterable, paginated, read-only view of the immutable audit log. */
export function AuditExplorer() {
  const [resourceType, setResourceType] = useState("");
  const [action, setAction] = useState("");
  const [actorId, setActorId] = useState("");
  const [applied, setApplied] = useState<{ resource_type?: string; action?: string; actor_id?: string }>({});
  const [offset, setOffset] = useState(0);

  const query = useAuditLog({ ...applied, limit: PAGE, offset });
  const rows = query.data?.results ?? [];
  const total = query.data?.count ?? 0;

  function applyFilters() {
    setOffset(0);
    setApplied({
      resource_type: resourceType.trim() || undefined,
      action: action.trim() || undefined,
      actor_id: actorId.trim() || undefined,
    });
  }
  function clearFilters() {
    setResourceType("");
    setAction("");
    setActorId("");
    setOffset(0);
    setApplied({});
  }

  return (
    <div className="space-y-4">
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          applyFilters();
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="a-resource">Resource type</Label>
          <Input id="a-resource" value={resourceType} onChange={(e) => setResourceType(e.target.value)} placeholder="record, workflow…" className="h-9 w-40" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-action">Action</Label>
          <Input id="a-action" value={action} onChange={(e) => setAction(e.target.value)} placeholder="created, updated…" className="h-9 w-40" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-actor">Actor ID</Label>
          <Input id="a-actor" value={actorId} onChange={(e) => setActorId(e.target.value)} placeholder="user id" className="h-9 w-56 font-mono text-xs" />
        </div>
        <Button type="submit">Apply</Button>
        <Button type="button" variant="ghost" onClick={clearFilters}>
          Clear
        </Button>
      </form>

      {query.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : query.isError ? (
        <ErrorState title="Couldn't load the audit log" />
      ) : rows.length === 0 ? (
        <EmptyState title="No audit entries" description="No events match the current filters." />
      ) : (
        <ul className="space-y-1.5">
          {rows.map((e) => (
            <AuditRow key={e.id} entry={e} />
          ))}
        </ul>
      )}

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span aria-label="Audit range">
          {total === 0 ? "0" : `${offset + 1}–${Math.min(offset + PAGE, total)}`} of {total}
        </span>
        <span className="flex gap-2">
          <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - PAGE))}>
            Previous
          </Button>
          <Button variant="outline" size="sm" disabled={offset + PAGE >= total} onClick={() => setOffset((o) => o + PAGE)}>
            Next
          </Button>
        </span>
      </div>
    </div>
  );
}

function AuditRow({ entry }: { entry: AuditEntry }) {
  const [open, setOpen] = useState(false);
  const when = entry.occurred_at ? new Date(entry.occurred_at).toLocaleString() : "—";
  return (
    <li className="rounded-md border p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{entry.action}</Badge>
        <span className="font-medium">{entry.resource_type || "—"}</span>
        {entry.resource_id && <code className="text-xs text-muted-foreground">{entry.resource_id}</code>}
        <span className="text-muted-foreground">by {entry.actor_name || entry.actor_id || "system"}</span>
        <span className="ml-auto text-xs text-muted-foreground">{when}</span>
        {entry.changed_fields.length > 0 && (
          <Button variant="ghost" size="sm" aria-label={`Toggle changed fields for ${entry.id}`} onClick={() => setOpen((o) => !o)}>
            {entry.changed_fields.length} field(s)
          </Button>
        )}
      </div>
      {open && entry.changed_fields.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {entry.changed_fields.map((f) => (
            <Badge key={f} variant="secondary">
              {f}
            </Badge>
          ))}
        </div>
      )}
    </li>
  );
}
