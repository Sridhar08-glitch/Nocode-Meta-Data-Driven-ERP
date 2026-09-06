"use client";

import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Spinner } from "@/components/ui/spinner";
import { useArchivedWorkspaces, useRestoreWorkspace } from "@/lib/tenant/admin-hooks";

export default function ArchivedWorkspacesPage() {
  const { query, refresh } = useArchivedWorkspaces();
  const restore = useRestoreWorkspace();

  if (query.isLoading) return <div className="flex justify-center p-10"><Spinner /></div>;
  if (query.isError)
    return <ErrorState title="Couldn't load archived workspaces" action={{ label: "Retry", onClick: () => refresh() }} />;

  const archived = query.data ?? [];

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Archived workspaces</h1>
        <p className="text-sm text-muted-foreground">
          Workspaces you own that are archived or pending deletion. Restore to reactivate.
        </p>
      </div>
      {archived.length === 0 ? (
        <EmptyState title="Nothing archived" description="None of your workspaces are archived or deleted." />
      ) : (
        <ul className="divide-y rounded-lg border">
          {archived.map((w) => (
            <li key={w.id} className="flex items-center justify-between gap-3 p-4">
              <div>
                <div className="font-medium">{w.name}</div>
                <div className="text-xs text-muted-foreground">
                  {w.slug} · {w.is_active ? "deleted (recoverable)" : "archived"}
                </div>
              </div>
              <Button size="sm" variant="outline"
                onClick={() => restore.mutateAsync(w.slug).then(() => refresh())}>
                Restore
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
