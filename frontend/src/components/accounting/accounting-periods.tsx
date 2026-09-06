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
import type { AccountingPeriod } from "@/lib/ledger/api";
import {
  useClosePeriod,
  useCreatePeriod,
  useGenerateFiscalYear,
  usePeriods,
  useReopenPeriod,
} from "@/lib/ledger/hooks";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  open: "default",
  closed: "secondary",
  locked: "destructive",
};

/** Accounting periods (Phase P2.2) — open/close/lock posting windows. */
export function AccountingPeriods() {
  const periods = usePeriods();
  const close = useClosePeriod();
  const reopen = useReopenPeriod();
  const genYear = useGenerateFiscalYear();
  const [creating, setCreating] = useState(false);

  const rows = periods.data ?? [];

  async function doGenerateYear() {
    const year = new Date().getFullYear();
    try {
      const r = await genYear.mutateAsync({ year });
      toast.success(`Created ${r.created} period${r.created === 1 ? "" : "s"} for ${year}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not generate year");
    }
  }

  async function act(fn: Promise<unknown>, ok: string) {
    try {
      await fn;
      toast.success(ok);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    }
  }

  if (periods.isLoading) return <Skeleton className="h-48 w-full" />;
  if (periods.isError) return <ErrorState title="Couldn't load periods" />;

  return (
    <div className="space-y-3">
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={doGenerateYear} disabled={genYear.isPending}>
          {genYear.isPending ? "Generating…" : `Generate ${new Date().getFullYear()}`}
        </Button>
        <Button onClick={() => setCreating(true)}>New period</Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No periods" description="Define posting windows to control when entries can be booked."
          action={{ label: "New period", onClick: () => setCreating(true) }} />
      ) : (
        <ul className="space-y-2">
          {rows.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-mono font-medium">{p.code}</span>
                <Badge variant={STATUS_VARIANT[p.status]}>{p.status}</Badge>
                <span className="text-muted-foreground">{p.start_date} → {p.end_date}</span>
              </span>
              <span className="flex items-center gap-1.5">
                {p.status === "open" && (
                  <>
                    <Button variant="ghost" size="sm" aria-label={`Close ${p.code}`}
                      onClick={() => act(close.mutateAsync({ id: p.id }), "Period closed")} disabled={close.isPending}>
                      Close
                    </Button>
                    <Button variant="ghost" size="sm" aria-label={`Lock ${p.code}`}
                      onClick={() => act(close.mutateAsync({ id: p.id, lock: true }), "Period locked")} disabled={close.isPending}>
                      Lock
                    </Button>
                  </>
                )}
                {p.status === "closed" && (
                  <Button variant="ghost" size="sm" aria-label={`Reopen ${p.code}`}
                    onClick={() => act(reopen.mutateAsync(p.id), "Period reopened")} disabled={reopen.isPending}>
                    Reopen
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {creating && <PeriodDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

function PeriodDialog({ onClose }: { onClose: () => void }) {
  const create = useCreatePeriod();
  const [form, setForm] = useState<Partial<AccountingPeriod>>({ code: "", start_date: "", end_date: "", name: "" });

  async function save() {
    try {
      await create.mutateAsync(form);
      toast.success("Period created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create period");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>New period</DialogTitle></DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="p-code">Code</Label>
            <Input id="p-code" value={form.code ?? ""} onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))} placeholder="2026-06" />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="p-start">Start</Label>
              <Input id="p-start" type="date" value={form.start_date ?? ""} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
            </div>
            <div className="flex-1">
              <Label htmlFor="p-end">End</Label>
              <Input id="p-end" type="date" value={form.end_date ?? ""} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={create.isPending || !form.code || !form.start_date || !form.end_date}>
            {create.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
