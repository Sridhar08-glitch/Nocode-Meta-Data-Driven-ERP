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
import type { AccountType, LedgerAccount } from "@/lib/ledger/api";
import { useCreateAccount, useDeleteAccount, useLedgerAccounts, useSeedChart } from "@/lib/ledger/hooks";

const TYPES: AccountType[] = ["asset", "liability", "equity", "revenue", "expense"];

/** Chart of accounts (Phase P2.2) — list grouped by type + create/deactivate. The full COA
 * tree, standard-chart seeding, and account groups arrive with the P2.3 accounting engine. */
export function ChartOfAccounts() {
  const accounts = useLedgerAccounts();
  const del = useDeleteAccount();
  const seed = useSeedChart();
  const [creating, setCreating] = useState(false);

  const rows = accounts.data ?? [];

  async function doSeed() {
    try {
      const r = await seed.mutateAsync();
      toast.success(`Seeded ${r.created} account${r.created === 1 ? "" : "s"}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not seed chart");
    }
  }

  async function doDelete(a: LedgerAccount) {
    try {
      await del.mutateAsync(a.id);
      toast.success("Account deleted");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Account has postings — deactivate instead");
    }
  }

  if (accounts.isLoading) return <Skeleton className="h-64 w-full" />;
  if (accounts.isError) return <ErrorState title="Couldn't load accounts" />;

  return (
    <div className="space-y-3">
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={doSeed} disabled={seed.isPending}>
          {seed.isPending ? "Seeding…" : "Seed standard chart"}
        </Button>
        <Button onClick={() => setCreating(true)}>New account</Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No accounts"
          description="Add accounts manually, or seed a standard small-business chart to get started instantly."
          action={{ label: "Seed standard chart", onClick: doSeed }} />
      ) : (
        TYPES.map((type) => {
          const inType = rows.filter((a) => a.account_type === type);
          if (inType.length === 0) return null;
          return (
            <section key={type} className="space-y-1">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{type}</h3>
              <ul className="space-y-1">
                {inType.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-muted-foreground">{a.code}</span>
                      <span>{a.name}</span>
                      {a.is_group && <Badge variant="outline">group</Badge>}
                      {!a.is_active && <Badge variant="destructive">inactive</Badge>}
                    </span>
                    <span className="flex items-center gap-2">
                      <Badge variant="secondary">{a.normal_balance}</Badge>
                      <Button variant="ghost" size="sm" aria-label={`Delete ${a.code}`}
                        onClick={() => doDelete(a)} disabled={del.isPending}>Delete</Button>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          );
        })
      )}
      {creating && <AccountDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

function AccountDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateAccount();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("asset");
  const [isGroup, setIsGroup] = useState(false);

  async function save() {
    try {
      await create.mutateAsync({ code: code.trim(), name: name.trim(), account_type: type, is_group: isGroup });
      toast.success("Account created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create account");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New account</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="w-32">
              <Label htmlFor="acct-code">Code</Label>
              <Input id="acct-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="1000" />
            </div>
            <div className="flex-1">
              <Label htmlFor="acct-name">Name</Label>
              <Input id="acct-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Cash" />
            </div>
          </div>
          <div>
            <Label htmlFor="acct-type">Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as AccountType)}>
              <SelectTrigger id="acct-type" aria-label="Account type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPES.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={isGroup} onChange={(e) => setIsGroup(e.target.checked)} />
            Group / header (not postable)
          </label>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={create.isPending || !code.trim() || !name.trim()}>
            {create.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
