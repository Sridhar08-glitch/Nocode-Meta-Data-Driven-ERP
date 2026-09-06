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
import { Switch } from "@/components/ui/switch";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { NumberSequence, NumberSequenceWrite, ResetScope } from "@/lib/numbering/api";
import {
  useAllocateNumber,
  useCreateSequence,
  useDeleteSequence,
  useNumberSequences,
  useResetSequence,
  useSequenceAllocations,
  useUpdateSequence,
} from "@/lib/numbering/hooks";

const RESET_SCOPES: ResetScope[] = ["never", "yearly", "monthly", "daily"];

function preview(s: Pick<NumberSequence, "prefix" | "suffix" | "padding" | "start_value" | "reset_scope" | "include_period_in_format">): string {
  const body = String(s.start_value).padStart(s.padding, "0");
  const period = s.include_period_in_format && s.reset_scope !== "never" ? "2026-" : "";
  return `${s.prefix}${period}${body}${s.suffix}`;
}

/** Numbering Engine admin (Phase P2.1) — manage gapless document-number sequences. */
export function NumberingManager() {
  const sequences = useNumberSequences();
  const del = useDeleteSequence();
  const allocate = useAllocateNumber();
  const reset = useResetSequence();
  const [editing, setEditing] = useState<NumberSequence | "new" | null>(null);
  const [logFor, setLogFor] = useState<NumberSequence | null>(null);

  const rows = sequences.data ?? [];

  async function doAllocate(s: NumberSequence) {
    try {
      const r = await allocate.mutateAsync(s.id);
      toast.success(`Allocated ${r.formatted}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not allocate");
    }
  }
  async function doReset(s: NumberSequence) {
    try {
      await reset.mutateAsync(s.id);
      toast.success(`Reset ${s.key}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not reset");
    }
  }
  async function doDelete(s: NumberSequence) {
    try {
      await del.mutateAsync(s.id);
      toast.success("Sequence deleted");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete");
    }
  }

  if (sequences.isLoading) return <Skeleton className="h-64 w-full" />;
  if (sequences.isError) return <ErrorState title="Couldn't load sequences" />;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setEditing("new")}>New sequence</Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No number sequences"
          description="Create a sequence (e.g. INV- for invoices). Finance modules auto-register their own."
          action={{ label: "New sequence", onClick: () => setEditing("new") }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex min-w-0 flex-wrap items-center gap-2">
                <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{s.key}</code>
                <span className="font-mono text-muted-foreground">{preview(s)}</span>
                {s.reset_scope !== "never" && <Badge variant="outline">resets {s.reset_scope}</Badge>}
                {s.is_system && <Badge variant="secondary">system</Badge>}
                {!s.is_active && <Badge variant="destructive">inactive</Badge>}
                <span className="text-xs text-muted-foreground">last #{s.current_value || "—"}</span>
              </span>
              <span className="flex shrink-0 items-center gap-1.5">
                <Button variant="ghost" size="sm" aria-label={`Allocate from ${s.key}`} onClick={() => doAllocate(s)} disabled={allocate.isPending}>
                  Allocate
                </Button>
                <Button variant="ghost" size="sm" aria-label={`History for ${s.key}`} onClick={() => setLogFor(s)}>
                  History
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Reset ${s.key}`} onClick={() => doReset(s)} disabled={reset.isPending}>
                  Reset
                </Button>
                <Button variant="ghost" size="sm" aria-label={`Edit ${s.key}`} onClick={() => setEditing(s)}>
                  Edit
                </Button>
                {!s.is_system && (
                  <Button variant="ghost" size="sm" aria-label={`Delete ${s.key}`} onClick={() => doDelete(s)} disabled={del.isPending}>
                    Delete
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {editing && <SequenceDialog sequence={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      {logFor && <AllocationsDialog sequence={logFor} onClose={() => setLogFor(null)} />}
    </div>
  );
}

function SequenceDialog({ sequence, onClose }: { sequence: NumberSequence | null; onClose: () => void }) {
  const create = useCreateSequence();
  const update = useUpdateSequence();
  const isNew = sequence === null;
  const [form, setForm] = useState<NumberSequenceWrite>({
    key: sequence?.key ?? "",
    name: sequence?.name ?? "",
    prefix: sequence?.prefix ?? "",
    suffix: sequence?.suffix ?? "",
    padding: sequence?.padding ?? 6,
    start_value: sequence?.start_value ?? 1,
    increment: sequence?.increment ?? 1,
    reset_scope: sequence?.reset_scope ?? "never",
    include_period_in_format: sequence?.include_period_in_format ?? false,
    is_active: sequence?.is_active ?? true,
  });

  function set<K extends keyof NumberSequenceWrite>(k: K, v: NumberSequenceWrite[K]) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function save() {
    try {
      if (isNew) {
        await create.mutateAsync(form);
        toast.success("Sequence created");
      } else {
        const { key: _key, ...rest } = form;
        void _key; // key is immutable after creation
        await update.mutateAsync({ id: sequence.id, data: rest });
        toast.success("Sequence updated");
      }
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save");
    }
  }

  const busy = create.isPending || update.isPending;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isNew ? "New sequence" : `Edit ${sequence.key}`}</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <Label htmlFor="key">Key</Label>
            <Input id="key" value={form.key} disabled={!isNew}
              onChange={(e) => set("key", e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))}
              placeholder="invoice" />
          </div>
          <div>
            <Label htmlFor="prefix">Prefix</Label>
            <Input id="prefix" value={form.prefix} onChange={(e) => set("prefix", e.target.value)} placeholder="INV-" />
          </div>
          <div>
            <Label htmlFor="suffix">Suffix</Label>
            <Input id="suffix" value={form.suffix} onChange={(e) => set("suffix", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="padding">Padding</Label>
            <Input id="padding" type="number" value={form.padding}
              onChange={(e) => set("padding", Number(e.target.value))} />
          </div>
          <div>
            <Label htmlFor="start">Start value</Label>
            <Input id="start" type="number" value={form.start_value}
              onChange={(e) => set("start_value", Number(e.target.value))} />
          </div>
          <div>
            <Label htmlFor="increment">Increment</Label>
            <Input id="increment" type="number" value={form.increment}
              onChange={(e) => set("increment", Number(e.target.value))} />
          </div>
          <div>
            <Label htmlFor="reset">Reset</Label>
            <Select value={form.reset_scope} onValueChange={(v) => set("reset_scope", v as ResetScope)}>
              <SelectTrigger id="reset" aria-label="Reset scope">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RESET_SCOPES.map((s) => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <label className="col-span-2 flex items-center gap-2 text-sm">
            <Switch checked={!!form.include_period_in_format}
              onCheckedChange={(v) => set("include_period_in_format", v)} aria-label="Include period in number" />
            Embed period (e.g. INV-2026-000001)
          </label>
          <p className="col-span-2 text-xs text-muted-foreground">
            Preview: <span className="font-mono">{preview({
              prefix: form.prefix ?? "", suffix: form.suffix ?? "", padding: form.padding ?? 6,
              start_value: form.start_value ?? 1, reset_scope: form.reset_scope ?? "never",
              include_period_in_format: !!form.include_period_in_format,
            })}</span>
          </p>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={busy || !form.key.trim()}>
            {busy ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AllocationsDialog({ sequence, onClose }: { sequence: NumberSequence; onClose: () => void }) {
  const log = useSequenceAllocations(sequence.id);
  const rows = log.data?.results ?? [];
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Allocation history — {sequence.key}</DialogTitle>
        </DialogHeader>
        {log.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">No numbers allocated yet.</p>
        ) : (
          <ul className="max-h-[50vh] space-y-1 overflow-y-auto text-sm">
            {rows.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-2 rounded border px-2 py-1">
                <span className="font-mono">{a.formatted}</span>
                <span className="text-xs text-muted-foreground">
                  {a.created_at ? new Date(a.created_at).toLocaleString() : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
