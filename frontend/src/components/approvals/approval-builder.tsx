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
import {
  type ApprovalLevel,
  APPROVER_TYPE_OPTIONS,
  type ApproverType,
  ON_TIMEOUT_OPTIONS,
  type OnTimeout,
  type Quorum,
  QUORUM_OPTIONS,
} from "@/lib/approvals/api";
import { useApprovalProcesses, useCreateProcess, useDeleteProcess } from "@/lib/approvals/hooks";
import { useEntities } from "@/lib/metadata/hooks";
import { isValidSlug, slugify } from "@/lib/metadata/slug";

const emptyLevel = (n: number): ApprovalLevel => ({
  level: n,
  approvers: [{ type: "role", value: "" }],
  quorum: "any",
  timeout_hours: 24,
  on_timeout: "auto_reject",
});

/** Approval matrix config (Phase F2.4): process → ordered levels of approvers with quorum + timeout. */
export function ApprovalBuilder() {
  const procs = useApprovalProcesses();
  const del = useDeleteProcess();
  const [adding, setAdding] = useState(false);

  if (procs.isLoading) return <Skeleton className="h-64 w-full" />;
  if (procs.isError) return <ErrorState title="Couldn't load approval processes" />;
  const rows = procs.data?.results ?? [];

  async function remove(id: string) {
    try {
      await del.mutateAsync(id);
      toast.success("Process removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove process");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground">{rows.length} approval processes</h2>
        <Button size="sm" onClick={() => setAdding(true)}>
          New process
        </Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No approval processes" description="Define who approves what, and in what order." action={{ label: "New process", onClick: () => setAdding(true) }} />
      ) : (
        <ul className="space-y-2">
          {rows.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{p.name}</span>
                <Badge variant="outline">{p.levels.length} level(s)</Badge>
                {!p.is_active && <Badge variant="secondary">inactive</Badge>}
              </span>
              <Button variant="ghost" size="sm" aria-label={`Remove process ${p.name}`} onClick={() => remove(p.id)} disabled={del.isPending}>
                Delete
              </Button>
            </li>
          ))}
        </ul>
      )}
      {adding && <ProcessDialog open onOpenChange={setAdding} />}
    </div>
  );
}

function ProcessDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const entities = useEntities();
  const create = useCreateProcess();
  const [name, setName] = useState("");
  const [entityId, setEntityId] = useState("");
  const [levels, setLevels] = useState<ApprovalLevel[]>([emptyLevel(1)]);
  const slug = slugify(name);
  const valid = !!name.trim() && isValidSlug(slug) && !!entityId && levels.every((l) => l.approvers.every((a) => a.value.trim()));

  const patchLevel = (i: number, patch: Partial<ApprovalLevel>) =>
    setLevels((ls) => ls.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  const patchApprover = (li: number, ai: number, patch: Partial<{ type: ApproverType; value: string }>) =>
    setLevels((ls) => ls.map((l, j) => (j === li ? { ...l, approvers: l.approvers.map((a, k) => (k === ai ? { ...a, ...patch } : a)) } : l)));

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({ name: name.trim(), slug, entity_id: entityId, levels });
      toast.success("Process created");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create process");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New approval process</DialogTitle>
        </DialogHeader>
        <div className="max-h-[60vh] space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="proc-name">Name</Label>
              <Input id="proc-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="proc-entity">Entity</Label>
              <Select value={entityId || undefined} onValueChange={setEntityId}>
                <SelectTrigger id="proc-entity" className="w-44">
                  <SelectValue placeholder="Pick entity" />
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
          </div>

          {levels.map((lvl, li) => (
            <div key={li} className="space-y-2 rounded-md border p-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Level {lvl.level}</span>
                {levels.length > 1 && (
                  <Button variant="ghost" size="sm" aria-label={`Remove level ${lvl.level}`} onClick={() => setLevels((ls) => ls.filter((_, j) => j !== li).map((l, j) => ({ ...l, level: j + 1 })))}>
                    ✕
                  </Button>
                )}
              </div>
              {lvl.approvers.map((a, ai) => (
                <div key={ai} className="flex flex-wrap items-center gap-2">
                  <Select value={a.type} onValueChange={(v) => patchApprover(li, ai, { type: v as ApproverType })}>
                    <SelectTrigger aria-label={`Level ${lvl.level} approver ${ai + 1} type`} className="h-8 w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {APPROVER_TYPE_OPTIONS.map((o) => (
                        <SelectItem key={o.value} value={o.value}>
                          {o.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input aria-label={`Level ${lvl.level} approver ${ai + 1} value`} className="h-8 w-40" placeholder="role / member id / field" value={a.value} onChange={(e) => patchApprover(li, ai, { value: e.target.value })} />
                  <Button variant="ghost" size="sm" aria-label={`Remove level ${lvl.level} approver ${ai + 1}`} onClick={() => patchLevel(li, { approvers: lvl.approvers.filter((_, k) => k !== ai) })}>
                    ✕
                  </Button>
                </div>
              ))}
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => patchLevel(li, { approvers: [...lvl.approvers, { type: "role", value: "" }] })}>
                  Add approver
                </Button>
                <Select value={lvl.quorum} onValueChange={(v) => patchLevel(li, { quorum: v as Quorum })}>
                  <SelectTrigger aria-label={`Level ${lvl.level} quorum`} className="h-8 w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {QUORUM_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input aria-label={`Level ${lvl.level} timeout hours`} type="number" className="h-8 w-24" value={lvl.timeout_hours ?? 0} onChange={(e) => patchLevel(li, { timeout_hours: Number(e.target.value) })} />
                <Select value={lvl.on_timeout} onValueChange={(v) => patchLevel(li, { on_timeout: v as OnTimeout })}>
                  <SelectTrigger aria-label={`Level ${lvl.level} on timeout`} className="h-8 w-36">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ON_TIMEOUT_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={() => setLevels((ls) => [...ls, emptyLevel(ls.length + 1)])}>
            Add level
          </Button>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "Creating…" : "Create process"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
