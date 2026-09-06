"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { MrpRun } from "@/lib/manufacturing/api";
import { useCanManageManufacturing, useRunMrp } from "@/lib/manufacturing/hooks";

interface DemandRow {
  item_id: string;
  demand: string;
  available: string;
}

const ACTION_VARIANT: Record<string, "default" | "secondary" | "success" | "destructive"> = {
  manufacture: "default",
  purchase: "destructive",
  none: "secondary",
};

/** MRP planning run (Phase P2.12) — enter demand rows, run the net-requirement calculation
 * server-side, and read back per-item suggested action (manufacture / purchase / none). */
export function MrpPanel() {
  const runMrp = useRunMrp();
  const canManage = useCanManageManufacturing();
  const [rows, setRows] = useState<DemandRow[]>([{ item_id: "", demand: "0", available: "0" }]);
  const [result, setResult] = useState<MrpRun | null>(null);

  function update(i: number, patch: Partial<DemandRow>) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    setRows((rs) => [...rs, { item_id: "", demand: "0", available: "0" }]);
  }
  function removeRow(i: number) {
    setRows((rs) => (rs.length === 1 ? rs : rs.filter((_, idx) => idx !== i)));
  }

  const validRows = rows.filter((r) => r.item_id.trim());

  async function run() {
    try {
      const res = await runMrp.mutateAsync(
        validRows.map((r) => ({
          item_id: r.item_id.trim(),
          demand: r.demand.trim() || "0",
          available: r.available.trim() || undefined,
        })),
      );
      setResult(res);
      toast.success(`MRP run complete — ${res.shortages} shortage(s)`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not run MRP");
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium">Demand</h2>
            <p className="text-sm text-muted-foreground">
              Add item ids (raw Inventory Item UUIDs) with demand and on-hand availability.
            </p>
          </div>
          <Button type="button" size="sm" variant="outline" onClick={addRow}>
            Add row
          </Button>
        </div>
        <div className="space-y-2">
          {rows.map((r, i) => (
            <div key={i} className="flex flex-wrap items-end gap-2">
              <div className="flex-1 min-w-[14rem]">
                <Label htmlFor={`mrp-item-${i}`} className="text-xs">Item id</Label>
                <Input
                  id={`mrp-item-${i}`}
                  value={r.item_id}
                  onChange={(e) => update(i, { item_id: e.target.value })}
                  placeholder="Inventory Item UUID"
                />
              </div>
              <div className="w-28">
                <Label htmlFor={`mrp-demand-${i}`} className="text-xs">Demand</Label>
                <Input
                  id={`mrp-demand-${i}`}
                  value={r.demand}
                  onChange={(e) => update(i, { demand: e.target.value })}
                  inputMode="decimal"
                />
              </div>
              <div className="w-28">
                <Label htmlFor={`mrp-avail-${i}`} className="text-xs">Available</Label>
                <Input
                  id={`mrp-avail-${i}`}
                  value={r.available}
                  onChange={(e) => update(i, { available: e.target.value })}
                  inputMode="decimal"
                />
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => removeRow(i)}
                disabled={rows.length === 1}
                aria-label={`Remove demand row ${i + 1}`}
              >
                Remove
              </Button>
            </div>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          {canManage && (
            <Button onClick={run} disabled={runMrp.isPending || validRows.length === 0}>
              {runMrp.isPending ? "Running…" : "Run MRP"}
            </Button>
          )}
        </div>
      </div>

      {runMrp.isPending ? (
        <Skeleton className="h-32 w-full" />
      ) : result ? (
        <div>
          <h3 className="mb-2 text-sm font-medium">
            Results <span className="text-muted-foreground">({result.shortages} shortage(s))</span>
          </h3>
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Item id</th>
                  <th className="px-3 py-2 text-right">Demand</th>
                  <th className="px-3 py-2 text-right">Available</th>
                  <th className="px-3 py-2 text-right">Net requirement</th>
                  <th className="px-3 py-2 text-right">Suggested qty</th>
                  <th className="px-3 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {result.results.map((row) => (
                  <tr key={row.item_id} className="border-b last:border-0">
                    <td className="px-3 py-2 font-mono text-xs">{row.item_id}</td>
                    <td className="px-3 py-2 text-right font-mono">{row.demand}</td>
                    <td className="px-3 py-2 text-right font-mono">{row.available}</td>
                    <td className="px-3 py-2 text-right font-mono">{row.net_requirement}</td>
                    <td className="px-3 py-2 text-right font-mono">{row.suggested_qty}</td>
                    <td className="px-3 py-2">
                      <Badge variant={ACTION_VARIANT[row.action] ?? "secondary"}>{row.action}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
