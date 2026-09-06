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
import type { Disposal, DisposalMethod } from "@/lib/assets/api";
import { useCreateDisposal, useDisposals } from "@/lib/assets/hooks";
import { useTenant } from "@/lib/tenant/context";

const METHODS: { value: DisposalMethod; label: string }[] = [
  { value: "sale", label: "Sale" },
  { value: "scrap", label: "Scrap" },
  { value: "donation", label: "Donation" },
  { value: "write_off", label: "Write off" },
];

function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/** Native disposal engine (Phase P2.9) — record an asset disposal (sale/scrap/donation/write-off).
 * The gain or loss vs. net book value is computed server-side. Creating a disposal is admin-gated. */
export function DisposalPanel() {
  const canManage = useCanManage();
  return (
    <div className="space-y-6">
      {canManage && <CreateDisposalForm />}
      <DisposalsList />
    </div>
  );
}

export function CreateDisposalForm() {
  const create = useCreateDisposal();
  const [assetRecordId, setAssetRecordId] = useState("");
  const [method, setMethod] = useState<DisposalMethod>("sale");
  const [proceeds, setProceeds] = useState("");
  const [bookValue, setBookValue] = useState("");
  const [reason, setReason] = useState("");

  async function save() {
    const asset = assetRecordId.trim();
    if (!asset || !reason.trim()) {
      toast.error("Asset record id and a reason are required");
      return;
    }
    try {
      await create.mutateAsync({
        asset_record_id: asset,
        method,
        proceeds: proceeds.trim() || "0",
        book_value: bookValue.trim() || undefined,
        reason: reason.trim(),
      });
      toast.success("Disposal recorded");
      setAssetRecordId("");
      setProceeds("");
      setBookValue("");
      setReason("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not record disposal");
    }
  }

  return (
    <div className="max-w-2xl space-y-3 rounded-lg border p-4">
      <h2 className="text-sm font-medium">Record a disposal</h2>
      <p className="text-xs text-muted-foreground">Enter the asset record id (raw UUID — no picker yet).</p>
      <div>
        <Label htmlFor="dis-asset">Asset record id</Label>
        <Input id="dis-asset" value={assetRecordId} onChange={(e) => setAssetRecordId(e.target.value)} placeholder="asset record id" />
      </div>
      <div className="flex flex-wrap gap-3">
        <div className="w-44">
          <Label htmlFor="dis-method">Method</Label>
          <Select value={method} onValueChange={(v) => setMethod(v as DisposalMethod)}>
            <SelectTrigger id="dis-method" aria-label="Disposal method">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METHODS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-40">
          <Label htmlFor="dis-proceeds">Proceeds</Label>
          <Input id="dis-proceeds" inputMode="decimal" value={proceeds} onChange={(e) => setProceeds(e.target.value)} placeholder="1500" />
        </div>
        <div className="w-40">
          <Label htmlFor="dis-book">Book value (optional)</Label>
          <Input id="dis-book" inputMode="decimal" value={bookValue} onChange={(e) => setBookValue(e.target.value)} placeholder="auto" />
        </div>
        <div className="flex-1">
          <Label htmlFor="dis-reason">Reason</Label>
          <Input id="dis-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Sold to vendor" />
        </div>
      </div>
      <div className="flex justify-end">
        <Button onClick={save} disabled={create.isPending}>
          {create.isPending ? "Saving…" : "Record disposal"}
        </Button>
      </div>
    </div>
  );
}

export function DisposalsList() {
  const [filter, setFilter] = useState("");
  const disposals = useDisposals(filter.trim() || undefined);
  const rows = disposals.data ?? [];

  return (
    <div className="space-y-3">
      <label className="w-72 space-y-1">
        <span className="text-xs font-medium">Filter by asset record id</span>
        <Input aria-label="Filter disposals by asset record id" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="asset record id" />
      </label>

      {disposals.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : disposals.isError ? (
        <ErrorState title="Couldn't load disposals" />
      ) : rows.length === 0 ? (
        <EmptyState title="No disposals" description="Record a disposal above to see it here." />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Asset</th>
                <th className="px-3 py-2">Method</th>
                <th className="px-3 py-2 text-right">Proceeds</th>
                <th className="px-3 py-2 text-right">Book value</th>
                <th className="px-3 py-2 text-right">Gain / loss</th>
                <th className="px-3 py-2">Reason</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d: Disposal) => (
                <tr key={d.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-muted-foreground">{d.asset_record_id.slice(0, 8)}</td>
                  <td className="px-3 py-2">
                    <Badge variant="secondary">{METHODS.find((m) => m.value === d.method)?.label ?? d.method}</Badge>
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{d.proceeds}</td>
                  <td className="px-3 py-2 text-right font-mono">{d.book_value}</td>
                  <td className={`px-3 py-2 text-right font-mono ${Number(d.gain_loss) < 0 ? "text-destructive" : "text-emerald-600"}`}>
                    {d.gain_loss}
                  </td>
                  <td className="px-3 py-2">{d.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
