"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useCommits, usePublish, useRollback } from "@/lib/config-vcs/hooks";

/** Draft→Publish bar (Phase F1.8): commit the live config; rollback a prior commit. */
export function PublishBar() {
  const commits = useCommits();
  const publish = usePublish();
  const rollback = useRollback();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");

  async function doPublish() {
    if (!message.trim()) return;
    try {
      const commit = await publish.mutateAsync({ message: message.trim() });
      toast.success(`Published ${commit.sha.slice(0, 8)}`);
      setOpen(false);
      setMessage("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) {
        toast.info("Nothing to publish — no configuration changes.");
      } else {
        toast.error(err instanceof ApiError ? err.message : "Could not publish");
      }
    }
  }

  async function doRollback(sha: string) {
    try {
      await rollback.mutateAsync(sha);
      toast.success(`Rolled back to ${sha.slice(0, 8)}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not roll back");
    }
  }

  const history = commits.data?.results ?? [];

  return (
    <div className="flex items-center gap-3">
      <Button onClick={() => setOpen(true)}>Publish changes</Button>
      {history.length > 0 && (
        <details className="relative">
          <summary className="cursor-pointer text-sm text-muted-foreground">
            History ({history.length})
          </summary>
          <ul className="absolute right-0 z-10 mt-2 w-80 space-y-1 rounded-md border bg-popover p-2 shadow-md">
            {history.map((c) => (
              <li key={c.sha} className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">
                  <span className="font-mono text-xs text-muted-foreground">
                    {c.sha.slice(0, 8)}
                  </span>{" "}
                  {c.message}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => doRollback(c.sha)}
                  disabled={rollback.isPending}
                >
                  Restore
                </Button>
              </li>
            ))}
          </ul>
        </details>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Publish configuration</DialogTitle>
            <DialogDescription>
              Snapshots the current config as a version. You can roll back later.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="commit-message">Message</Label>
            <Input
              id="commit-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Add Lead entity + intake form"
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={doPublish} disabled={!message.trim() || publish.isPending}>
              {publish.isPending ? "Publishing…" : "Publish"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
