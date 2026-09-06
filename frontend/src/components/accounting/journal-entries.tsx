"use client";

import { useMemo, useState } from "react";

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
import type { JournalEntry } from "@/lib/ledger/api";
import {
  useCreateEntry,
  useJournalEntries,
  useLedgerAccounts,
  useReverseEntry,
} from "@/lib/ledger/hooks";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  posted: "default",
  draft: "secondary",
  reversed: "destructive",
};

function money(v: string | number): string {
  const n = typeof v === "number" ? v : parseFloat(v || "0");
  return n.toFixed(2);
}

/** Journal entry runtime (Phase P2.2) — list + post (balanced line editor) + reverse. */
export function JournalEntries() {
  const entries = useJournalEntries();
  const reverse = useReverseEntry();
  const [creating, setCreating] = useState(false);

  const rows = entries.data ?? [];

  async function doReverse(e: JournalEntry) {
    try {
      await reverse.mutateAsync(e.id);
      toast.success("Entry reversed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not reverse");
    }
  }

  if (entries.isLoading) return <Skeleton className="h-64 w-full" />;
  if (entries.isError) return <ErrorState title="Couldn't load journal entries" />;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setCreating(true)}>New journal entry</Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No journal entries"
          description="Post a balanced double-entry transaction. Finance modules also post here automatically."
          action={{ label: "New journal entry", onClick: () => setCreating(true) }}
        />
      ) : (
        <ul className="space-y-2">
          {rows.map((e) => {
            const total = e.lines.reduce((s, l) => s + parseFloat(String(l.debit || 0)), 0);
            return (
              <li key={e.id} className="rounded-md border p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    <span className="font-mono font-medium">{e.entry_number || "(draft)"}</span>
                    <Badge variant={STATUS_VARIANT[e.status] ?? "outline"}>{e.status}</Badge>
                    <span className="text-muted-foreground">{e.date}</span>
                    {e.memo && <span className="text-muted-foreground">· {e.memo}</span>}
                    {e.source_module && e.source_module !== "manual" && (
                      <Badge variant="outline">{e.source_module}</Badge>
                    )}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="font-mono tabular-nums">{money(total)}</span>
                    {e.status === "posted" && (
                      <Button variant="ghost" size="sm" aria-label={`Reverse ${e.entry_number}`}
                        onClick={() => doReverse(e)} disabled={reverse.isPending}>
                        Reverse
                      </Button>
                    )}
                  </span>
                </div>
                <ul className="mt-2 space-y-0.5 text-xs">
                  {e.lines.map((l, i) => (
                    <li key={l.id ?? i} className="flex items-center gap-2">
                      <span className="font-mono text-muted-foreground">{l.account_code}</span>
                      <span className="flex-1 truncate">{l.account_name}</span>
                      <span className="w-24 text-right font-mono tabular-nums">
                        {parseFloat(String(l.debit)) > 0 ? money(l.debit) : ""}
                      </span>
                      <span className="w-24 text-right font-mono tabular-nums">
                        {parseFloat(String(l.credit)) > 0 ? money(l.credit) : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      )}

      {creating && <EntryDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

interface DraftLine {
  account_id: string;
  debit: string;
  credit: string;
  memo: string;
}
const emptyLine = (): DraftLine => ({ account_id: "", debit: "", credit: "", memo: "" });

function EntryDialog({ onClose }: { onClose: () => void }) {
  const accounts = useLedgerAccounts();
  const create = useCreateEntry();
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [memo, setMemo] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([emptyLine(), emptyLine()]);

  const postable = useMemo(() => (accounts.data ?? []).filter((a) => !a.is_group && a.is_active), [accounts.data]);
  const totals = useMemo(() => {
    const d = lines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0);
    const c = lines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
    return { d, c, balanced: d > 0 && Math.abs(d - c) < 0.005 };
  }, [lines]);

  function setLine(i: number, patch: Partial<DraftLine>) {
    setLines((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }

  async function save(post: boolean) {
    const payload = {
      date,
      memo,
      post,
      lines: lines
        .filter((l) => l.account_id && (parseFloat(l.debit) > 0 || parseFloat(l.credit) > 0))
        .map((l) => ({ account_id: l.account_id, debit: l.debit || 0, credit: l.credit || 0, memo: l.memo })),
    };
    try {
      await create.mutateAsync(payload);
      toast.success(post ? "Entry posted" : "Draft saved");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New journal entry</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex gap-3">
            <div>
              <label className="text-xs text-muted-foreground" htmlFor="je-date">Date</label>
              <Input id="je-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-40" />
            </div>
            <div className="flex-1">
              <label className="text-xs text-muted-foreground" htmlFor="je-memo">Memo</label>
              <Input id="je-memo" value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="Description" />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex gap-2 px-1 text-xs text-muted-foreground">
              <span className="flex-1">Account</span>
              <span className="w-24 text-right">Debit</span>
              <span className="w-24 text-right">Credit</span>
              <span className="w-6" />
            </div>
            {lines.map((l, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="flex-1">
                  <Select value={l.account_id} onValueChange={(v) => setLine(i, { account_id: v })}>
                    <SelectTrigger aria-label={`Line ${i + 1} account`}>
                      <SelectValue placeholder="Select account" />
                    </SelectTrigger>
                    <SelectContent>
                      {postable.map((a) => (
                        <SelectItem key={a.id} value={a.id}>{a.code} — {a.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Input aria-label={`Line ${i + 1} debit`} className="w-24 text-right" inputMode="decimal"
                  value={l.debit} onChange={(e) => setLine(i, { debit: e.target.value, credit: "" })} />
                <Input aria-label={`Line ${i + 1} credit`} className="w-24 text-right" inputMode="decimal"
                  value={l.credit} onChange={(e) => setLine(i, { credit: e.target.value, debit: "" })} />
                <Button variant="ghost" size="sm" className="w-6 px-0" aria-label={`Remove line ${i + 1}`}
                  onClick={() => setLines((ls) => (ls.length > 2 ? ls.filter((_, idx) => idx !== i) : ls))}>
                  ×
                </Button>
              </div>
            ))}
            <Button variant="ghost" size="sm" onClick={() => setLines((ls) => [...ls, emptyLine()])}>
              + Add line
            </Button>
          </div>

          <div className="flex items-center justify-end gap-4 border-t pt-2 text-sm">
            <span>Debits <span className="font-mono tabular-nums">{totals.d.toFixed(2)}</span></span>
            <span>Credits <span className="font-mono tabular-nums">{totals.c.toFixed(2)}</span></span>
            <Badge variant={totals.balanced ? "default" : "destructive"}>
              {totals.balanced ? "Balanced" : "Unbalanced"}
            </Badge>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="outline" onClick={() => save(false)} disabled={create.isPending}>Save draft</Button>
          <Button onClick={() => save(true)} disabled={create.isPending || !totals.balanced}>
            {create.isPending ? "Posting…" : "Post"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
