"use client";

import { useState } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { useStock, useValuation, useWarehouses } from "@/lib/inventory/hooks";

const ALL = "__all__";

/** Stock balance + valuation (Phase P2.4) — on-hand quantity, average unit cost, and total
 * value per item/warehouse. All figures are computed server-side from the cost ledger. */
export function StockBalance() {
  const warehouses = useWarehouses();
  const [warehouse, setWarehouse] = useState<string>(ALL);
  const wh = warehouse === ALL ? undefined : warehouse;
  const stock = useStock(wh ? { warehouse: wh } : undefined);
  const valuation = useValuation(wh);

  const rows = stock.data?.rows ?? [];
  const total = valuation.data?.total_value ?? "0";

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="w-64">
          <Select value={warehouse} onValueChange={setWarehouse}>
            <SelectTrigger aria-label="Filter by warehouse"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All warehouses</SelectItem>
              {(warehouses.data ?? []).map((w) => (
                <SelectItem key={w.id} value={w.id}>{w.code} — {w.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="text-sm">
          <span className="text-muted-foreground">Total value: </span>
          <span className="font-mono font-medium">{total}</span>
        </div>
      </div>

      {stock.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : stock.isError ? (
        <ErrorState title="Couldn't load stock" />
      ) : rows.length === 0 ? (
        <EmptyState title="No stock on hand" description="Receive inventory to see balances here." />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">SKU</th>
                <th className="px-3 py-2">Item</th>
                <th className="px-3 py-2">Warehouse</th>
                <th className="px-3 py-2 text-right">On hand</th>
                <th className="px-3 py-2 text-right">Avg cost</th>
                <th className="px-3 py-2 text-right">Value</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.item_id}:${r.warehouse_id}`} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-muted-foreground">{r.sku}</td>
                  <td className="px-3 py-2">{r.item_name}</td>
                  <td className="px-3 py-2">{r.warehouse_code}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.on_hand}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.avg_cost}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
