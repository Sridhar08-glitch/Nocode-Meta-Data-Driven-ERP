"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  useArchiveWorkspace,
  useConfirmHardDelete,
  useRequestHardDelete,
  useSoftDeleteWorkspace,
} from "@/lib/tenant/admin-hooks";
import { useTenant } from "@/lib/tenant/context";

/** Owner-only workspace lifecycle: archive · soft-delete · permanent delete (P2.17). */
export function WorkspaceDangerZone() {
  const { workspace } = useTenant();
  const archive = useArchiveWorkspace();
  const softDelete = useSoftDeleteWorkspace();
  const requestHard = useRequestHardDelete();
  const confirmHard = useConfirmHardDelete();
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  if (!workspace || workspace.role !== "owner") return null;
  const wsName = workspace.name;

  function leave() {
    // The current workspace is no longer usable — re-evaluate from the top.
    window.location.assign("/home");
  }
  function fail(err: unknown) {
    setError(err instanceof Error ? err.message : "Action failed.");
  }

  async function startHardDelete() {
    setError(null);
    try {
      const { confirmation_token } = await requestHard.mutateAsync();
      // Two-step: the backend already issued a one-time token; confirm immediately
      // after an explicit user confirmation.
      if (window.confirm(
        `Permanently delete "${wsName}"? This cannot be undone.`)) {
        await confirmHard.mutateAsync(confirmation_token);
        leave();
      }
      setConfirming(false);
    } catch (err) {
      fail(err);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-destructive/40 p-5">
      <div>
        <h2 className="font-medium text-destructive">Danger zone</h2>
        <p className="text-sm text-muted-foreground">
          Archive pauses the workspace; delete is recoverable for 30 days; permanent
          delete is irreversible.
        </p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="outline"
          onClick={() => archive.mutateAsync().then(leave).catch(fail)}>
          Archive workspace
        </Button>
        <Button variant="outline"
          onClick={() => {
            if (window.confirm("Delete this workspace? Recoverable for 30 days."))
              softDelete.mutateAsync().then(leave).catch(fail);
          }}>
          Delete (recoverable)
        </Button>
        {!confirming ? (
          <Button variant="destructive" onClick={() => setConfirming(true)}>
            Delete permanently…
          </Button>
        ) : (
          <Button variant="destructive" disabled={requestHard.isPending || confirmHard.isPending}
            onClick={startHardDelete}>
            Confirm permanent delete
          </Button>
        )}
      </div>
    </div>
  );
}
