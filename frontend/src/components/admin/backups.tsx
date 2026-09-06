"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import {
  type BackupType,
  type RestoreType,
  BACKUP_TYPES,
} from "@/lib/backups/api";
import {
  useBackupJobs,
  useConfirmRestore,
  useCreateBackup,
  useCreateRestore,
  useDeleteBackup,
} from "@/lib/backups/hooks";
import { useTenant } from "@/lib/tenant/context";

export function BackupsPanel() {
  return (
    <div className="space-y-8">
      <BackupJobs />
      <RestorePanel />
    </div>
  );
}

function fmtBytes(n: number): string {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / 1024 ** i).toFixed(1)} ${units[i]}`;
}

function BackupJobs() {
  const jobs = useBackupJobs();
  const create = useCreateBackup();
  const del = useDeleteBackup();
  const [type, setType] = useState<BackupType>("full");

  const rows = jobs.data?.results ?? [];

  async function run() {
    try {
      await create.mutateAsync(type);
      toast.success("Backup queued");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not start backup");
    }
  }
  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Backup deleted");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete backup");
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">Backup jobs</h2>
        <div className="flex items-end gap-2">
          <div className="space-y-1.5">
            <Label htmlFor="bk-type">Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as BackupType)}>
              <SelectTrigger id="bk-type" className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {BACKUP_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={run} disabled={create.isPending}>
            {create.isPending ? "Starting…" : "Create backup"}
          </Button>
        </div>
      </div>

      {jobs.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : jobs.isError ? (
        <ErrorState title="Couldn't load backups" />
      ) : rows.length === 0 ? (
        <EmptyState title="No backups yet" description="Create a full, incremental, or config-only backup." />
      ) : (
        <ul className="space-y-2">
          {rows.map((j) => (
            <li key={j.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{j.backup_type}</Badge>
                <Badge variant={j.status === "completed" ? "default" : j.status === "failed" ? "destructive" : "secondary"}>{j.status}</Badge>
                {j.is_encrypted && <Badge variant="secondary">encrypted</Badge>}
                <span className="text-xs text-muted-foreground">
                  {fmtBytes(j.size_bytes)} · {j.record_count} records · {j.created_at ? new Date(j.created_at).toLocaleString() : ""}
                </span>
              </span>
              <Button variant="ghost" size="sm" aria-label={`Delete backup ${j.id}`} onClick={() => remove(j.id)} disabled={del.isPending}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function RestorePanel() {
  const { workspace } = useTenant();
  const jobs = useBackupJobs();
  const create = useCreateRestore();
  const confirm = useConfirmRestore();

  const [restoreType, setRestoreType] = useState<RestoreType>("full");
  const [backupJobId, setBackupJobId] = useState("");
  const [sequence, setSequence] = useState("");
  const [targetId, setTargetId] = useState("");
  const [targetSlug, setTargetSlug] = useState("");
  const [pending, setPending] = useState<{ id: string; token: string } | null>(null);
  const [confirmToken, setConfirmToken] = useState("");

  const sourceId = workspace?.id ?? "";
  const sameWorkspace = !!targetId.trim() && targetId.trim() === sourceId;
  const valid =
    !!targetId.trim() &&
    !!targetSlug.trim() &&
    !sameWorkspace &&
    (restoreType === "full" ? !!backupJobId : !!sequence.trim());

  async function startRestore() {
    if (!valid) return;
    try {
      const res = await create.mutateAsync({
        restore_type: restoreType,
        backup_job_id: restoreType === "full" ? backupJobId : undefined,
        pitr_target_sequence: restoreType === "pitr" ? Number(sequence) : undefined,
        target_workspace_id: targetId.trim(),
        target_workspace_slug: targetSlug.trim(),
      });
      setPending({ id: res.id, token: res.confirmation_token });
      setConfirmToken(res.confirmation_token);
      toast.success("Restore created — confirm with the one-time token below");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create restore");
    }
  }
  async function confirmRestore() {
    if (!pending) return;
    try {
      await confirm.mutateAsync({ id: pending.id, token: confirmToken.trim() });
      toast.success("Restore confirmed and dispatched");
      setPending(null);
      setConfirmToken("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Confirmation failed (token mismatch?)");
    }
  }

  const backups = (jobs.data?.results ?? []).filter((j) => j.status === "completed");

  return (
    <section className="space-y-4 border-t pt-6">
      <h2 className="text-sm font-medium text-muted-foreground">Restore (point-in-time)</h2>
      <p className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground" role="note">
        A restore always lands in an <strong>isolated target workspace</strong> — never the source.
        Production is never overwritten.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="rs-type">Restore type</Label>
          <Select value={restoreType} onValueChange={(v) => setRestoreType(v as RestoreType)}>
            <SelectTrigger id="rs-type" className="w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="full">Full backup</SelectItem>
              <SelectItem value="pitr">Point-in-time</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {restoreType === "full" ? (
          <div className="space-y-1.5">
            <Label htmlFor="rs-backup">Backup</Label>
            <Select value={backupJobId || undefined} onValueChange={setBackupJobId}>
              <SelectTrigger id="rs-backup" className="w-56">
                <SelectValue placeholder="Pick a completed backup" />
              </SelectTrigger>
              <SelectContent>
                {backups.map((b) => (
                  <SelectItem key={b.id} value={b.id}>
                    {b.backup_type} · {b.created_at ? new Date(b.created_at).toLocaleDateString() : b.id.slice(0, 8)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : (
          <div className="space-y-1.5">
            <Label htmlFor="rs-seq">Target sequence</Label>
            <Input id="rs-seq" type="number" value={sequence} onChange={(e) => setSequence(e.target.value)} className="w-40" placeholder="event sequence" />
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="rs-target-id">Target workspace ID</Label>
          <Input id="rs-target-id" value={targetId} onChange={(e) => setTargetId(e.target.value)} className="w-72 font-mono text-xs" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="rs-target-slug">Target workspace slug</Label>
          <Input id="rs-target-slug" value={targetSlug} onChange={(e) => setTargetSlug(e.target.value)} className="w-44" />
        </div>
        <Button onClick={startRestore} disabled={!valid || create.isPending}>
          {create.isPending ? "Creating…" : "Create restore"}
        </Button>
      </div>
      {sameWorkspace && (
        <p role="alert" className="text-xs text-destructive">
          Target must be a different workspace than the current one — production can&apos;t be overwritten.
        </p>
      )}

      {pending && (
        <div className="space-y-2 rounded-md border border-amber-500/50 bg-amber-500/5 p-3">
          <p className="text-sm font-medium">One-time confirmation token</p>
          <p className="text-xs text-muted-foreground">
            This token is shown once. Confirm to dispatch the restore into the isolated target.
          </p>
          <code className="block break-all rounded bg-muted px-2 py-1 text-xs">{pending.token}</code>
          <div className="flex items-end gap-2">
            <div className="space-y-1.5">
              <Label htmlFor="rs-confirm">Token</Label>
              <Input id="rs-confirm" value={confirmToken} onChange={(e) => setConfirmToken(e.target.value)} className="w-72 font-mono text-xs" />
            </div>
            <Button onClick={confirmRestore} disabled={!confirmToken.trim() || confirm.isPending}>
              {confirm.isPending ? "Confirming…" : "Confirm restore"}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
