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
import type { ConfigCommit, ConfigDiff } from "@/lib/config-vcs/api";
import { useCommits, useDiff, usePublish, useRollback } from "@/lib/config-vcs/hooks";

const DIFF_KINDS = ["entities", "fields", "rules", "roles", "permissions"] as const;

function shortSha(sha: string) {
  return sha.slice(0, 8);
}
function labelOf(obj: unknown): string {
  if (obj && typeof obj === "object") {
    const o = obj as Record<string, unknown> & { after?: Record<string, unknown> };
    const src = o.after && typeof o.after === "object" ? o.after : o;
    return String(src.slug ?? src.name ?? src.id ?? JSON.stringify(src).slice(0, 40));
  }
  return String(obj);
}

/** Config VCS UI (Phase F3.3): commit history + commit + structural diff + rollback. */
export function ConfigVcsPanel() {
  const commits = useCommits("main");
  const publish = usePublish();
  const rollback = useRollback();
  const [committing, setCommitting] = useState(false);
  const [message, setMessage] = useState("");
  const [rollbackTarget, setRollbackTarget] = useState<ConfigCommit | null>(null);
  const [a, setA] = useState<string>("");
  const [b, setB] = useState<string>("");

  const rows = commits.data?.results ?? [];

  async function doCommit() {
    if (!message.trim()) return;
    try {
      await publish.mutateAsync({ message: message.trim() });
      toast.success("Configuration committed");
      setCommitting(false);
      setMessage("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Nothing to commit or commit failed");
    }
  }
  async function doRollback() {
    if (!rollbackTarget) return;
    try {
      await rollback.mutateAsync(rollbackTarget.sha);
      toast.success("Rolled back");
      setRollbackTarget(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Rollback failed");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">Commit history (main)</h2>
        <Button size="sm" onClick={() => setCommitting(true)}>
          Commit live config
        </Button>
      </div>

      {commits.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : commits.isError ? (
        <ErrorState title="Couldn't load commits" />
      ) : rows.length === 0 ? (
        <EmptyState title="No commits yet" description="Commit the live configuration to start version history." />
      ) : (
        <ul className="space-y-2">
          {rows.map((c) => (
            <li key={c.sha} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <code className="text-xs text-muted-foreground">{shortSha(c.sha)}</code>
                <span className="font-medium">{c.message || "(no message)"}</span>
                <span className="text-xs text-muted-foreground">{c.created_at ? new Date(c.created_at).toLocaleString() : ""}</span>
              </span>
              <Button variant="ghost" size="sm" aria-label={`Rollback to ${shortSha(c.sha)}`} onClick={() => setRollbackTarget(c)}>
                Rollback
              </Button>
            </li>
          ))}
        </ul>
      )}

      <DiffViewer commits={rows} a={a} b={b} onA={setA} onB={setB} />

      {/* Commit dialog */}
      <Dialog open={committing} onOpenChange={setCommitting}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Commit live configuration</DialogTitle>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="cv-msg">Message</Label>
            <Input id="cv-msg" value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Describe this change" autoFocus />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCommitting(false)}>
              Cancel
            </Button>
            <Button onClick={doCommit} disabled={!message.trim() || publish.isPending}>
              {publish.isPending ? "Committing…" : "Commit"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rollback confirm */}
      <Dialog open={!!rollbackTarget} onOpenChange={(o) => !o && setRollbackTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Roll back configuration?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This restores the workspace configuration to commit{" "}
            <code>{rollbackTarget ? shortSha(rollbackTarget.sha) : ""}</code> and records a new
            commit. Live metadata will change for everyone in this workspace.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRollbackTarget(null)}>
              Cancel
            </Button>
            <Button onClick={doRollback} disabled={rollback.isPending}>
              {rollback.isPending ? "Rolling back…" : "Roll back"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DiffViewer({
  commits,
  a,
  b,
  onA,
  onB,
}: {
  commits: ConfigCommit[];
  a: string;
  b: string;
  onA: (v: string) => void;
  onB: (v: string) => void;
}) {
  const diff = useDiff(a || null, b || null);

  return (
    <section className="space-y-3 border-t pt-5">
      <h2 className="text-sm font-medium text-muted-foreground">Compare commits</h2>
      <div className="flex flex-wrap items-end gap-2">
        <CommitSelect id="diff-a" label="From" value={a} onChange={onA} commits={commits} />
        <CommitSelect id="diff-b" label="To" value={b} onChange={onB} commits={commits} />
      </div>

      {a && b && a === b && <p className="text-sm text-muted-foreground">Pick two different commits.</p>}
      {diff.isLoading && <Skeleton className="h-24 w-full" />}
      {diff.isError && <ErrorState title="Couldn't load diff" />}
      {diff.data && <DiffBody diff={diff.data} />}
    </section>
  );
}

function CommitSelect({
  id,
  label,
  value,
  onChange,
  commits,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  commits: ConfigCommit[];
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Select value={value || undefined} onValueChange={onChange}>
        <SelectTrigger id={id} className="w-64">
          <SelectValue placeholder="Pick commit" />
        </SelectTrigger>
        <SelectContent>
          {commits.map((c) => (
            <SelectItem key={c.sha} value={c.sha}>
              {shortSha(c.sha)} — {c.message || "(no message)"}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function DiffBody({ diff }: { diff: ConfigDiff }) {
  const kinds = DIFF_KINDS.filter((k) => {
    const d = diff[k];
    return d && (d.added.length || d.removed.length || d.modified.length);
  });

  if (kinds.length === 0) return <p className="text-sm text-muted-foreground">No configuration differences.</p>;

  return (
    <div className="space-y-3">
      {kinds.map((kind) => {
        const d = diff[kind];
        return (
          <div key={kind} className="rounded-md border p-3" aria-label={`diff-${kind}`}>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium capitalize">
              {kind}
              {d.added.length > 0 && <Badge className="bg-emerald-600">+{d.added.length}</Badge>}
              {d.removed.length > 0 && <Badge variant="destructive">−{d.removed.length}</Badge>}
              {d.modified.length > 0 && <Badge variant="secondary">~{d.modified.length}</Badge>}
            </div>
            <ul className="space-y-0.5 text-xs">
              {d.added.map((o, i) => (
                <li key={`a${i}`} className="text-emerald-600">+ {labelOf(o)}</li>
              ))}
              {d.removed.map((o, i) => (
                <li key={`r${i}`} className="text-destructive">− {labelOf(o)}</li>
              ))}
              {d.modified.map((o, i) => (
                <li key={`m${i}`} className="text-muted-foreground">~ {labelOf(o)}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
