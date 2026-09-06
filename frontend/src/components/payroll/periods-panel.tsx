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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { PayPeriod, PeriodStatus } from "@/lib/payroll/api";
import {
  useCanManagePayroll,
  useClosePeriod,
  useCreatePeriod,
  useLockPeriod,
  useOpenPeriod,
  usePeriods,
  useReopenPeriod,
} from "@/lib/payroll/hooks";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "success" | "destructive"> = {
  draft: "secondary",
  open: "success",
  processing: "default",
  closed: "secondary",
  locked: "destructive",
};

/** Pay periods (Phase P2.8) — create + lifecycle (open / close / lock / reopen). Runs are created
 * against an open period. Lifecycle transitions are gated server-side. */
export function PeriodsPanel({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const periods = usePeriods();
  const canManage = useCanManagePayroll();
  const open = useOpenPeriod();
  const close = useClosePeriod();
  const lock = useLockPeriod();
  const reopen = useReopenPeriod();
  const [creating, setCreating] = useState(false);

  const rows = periods.data ?? [];

  async function transition(label: string, fn: () => Promise<unknown>) {
    try {
      await fn();
      toast.success(label);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update period");
    }
  }

  if (periods.isLoading) return <Skeleton className="h-48 w-full" />;
  if (periods.isError) return <ErrorState title="Couldn't load pay periods" />;

  const pending = open.isPending || close.isPending || lock.isPending || reopen.isPending;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Pay periods</h2>
        {canManage && <Button size="sm" onClick={() => setCreating(true)}>New period</Button>}
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No pay periods" description="Create a pay period to start a payroll run." />
      ) : (
        <ul className="space-y-1">
          {rows.map((p) => {
            const status = p.status as PeriodStatus;
            const active = p.id === selectedId;
            return (
              <li
                key={p.id}
                className={`rounded-md border px-3 py-2 text-sm ${active ? "border-primary bg-primary/5" : ""}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => onSelect(p.id)}
                    className="flex items-center gap-2 text-left"
                  >
                    <span className="font-medium">{p.name}</span>
                    <Badge variant={STATUS_VARIANT[status] ?? "secondary"}>{status}</Badge>
                    <span className="text-muted-foreground">{p.start_date} → {p.end_date}</span>
                  </button>
                  {canManage && (
                    <span className="flex flex-wrap gap-1">
                      {status === "draft" && (
                        <Button variant="outline" size="sm" disabled={pending}
                          onClick={() => transition("Period opened", () => open.mutateAsync(p.id))}>Open</Button>
                      )}
                      {status === "open" && (
                        <Button variant="outline" size="sm" disabled={pending}
                          onClick={() => transition("Period closed", () => close.mutateAsync(p.id))}>Close</Button>
                      )}
                      {status === "closed" && (
                        <>
                          <Button variant="outline" size="sm" disabled={pending}
                            onClick={() => transition("Period reopened", () => reopen.mutateAsync(p.id))}>Reopen</Button>
                          <Button variant="outline" size="sm" disabled={pending}
                            onClick={() => transition("Period locked", () => lock.mutateAsync(p.id))}>Lock</Button>
                        </>
                      )}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {creating && <PeriodDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

function PeriodDialog({ onClose }: { onClose: () => void }) {
  const create = useCreatePeriod();
  const [name, setName] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  async function save() {
    try {
      const created: PayPeriod = await create.mutateAsync({
        name: name.trim(),
        start_date: start,
        end_date: end,
      });
      toast.success(`Period "${created.name}" created`);
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create period");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New pay period</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="pp-name">Name</Label>
            <Input id="pp-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="January 2026" />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="pp-start">Start date</Label>
              <Input id="pp-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </div>
            <div className="flex-1">
              <Label htmlFor="pp-end">End date</Label>
              <Input id="pp-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={create.isPending || !name.trim() || !start || !end}>
            {create.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
