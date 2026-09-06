"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { MovementType } from "@/lib/inventory/api";
import { useItems, useMovements } from "@/lib/inventory/hooks";

const ALL = "__all__";

const MOVEMENT_VARIANT: Record<MovementType, "default" | "secondary" | "destructive" | "outline"> = {
  receipt: "default",
  issue: "destructive",
  adjustment: "secondary",
  transfer_in: "default",
  transfer_out: "outline",
};

/** Movement ledger (Phase P2.4) — immutable, append-only record of every stock change. */
export function MovementHistory() {
  const items = useItems();
  const [item, setItem] = useState<string>(ALL);
  const movements = useMovements(item === ALL ? undefined : { item });

  const rows = movements.data?.rows ?? [];

  return (
    <div className="space-y-3">
      <div className="w-72">
        <Select value={item} onValueChange={setItem}>
          <SelectTrigger aria-label="Filter by item"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All items</SelectItem>
            {(items.data ?? []).map((i) => (
              <SelectItem key={i.id} value={i.id}>{i.sku} — {i.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {movements.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : movements.isError ? (
        <ErrorState title="Couldn't load movements" />
      ) : rows.length === 0 ? (
        <EmptyState title="No movements" description="Stock transactions appear here as they are posted." />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">When</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">SKU</th>
                <th className="px-3 py-2">Warehouse</th>
                <th className="px-3 py-2 text-right">Qty</th>
                <th className="px-3 py-2 text-right">Unit cost</th>
                <th className="px-3 py-2 text-right">On hand after</th>
                <th className="px-3 py-2">Reference</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.id} className="border-b last:border-0">
                  <td className="px-3 py-2 text-muted-foreground">{new Date(m.occurred_at).toLocaleString()}</td>
                  <td className="px-3 py-2">
                    <Badge variant={MOVEMENT_VARIANT[m.movement_type]}>{m.movement_type.replace("_", " ")}</Badge>
                  </td>
                  <td className="px-3 py-2 font-mono text-muted-foreground">{m.sku}</td>
                  <td className="px-3 py-2">{m.warehouse_code}</td>
                  <td className="px-3 py-2 text-right font-mono">{m.quantity}</td>
                  <td className="px-3 py-2 text-right font-mono">{m.unit_cost}</td>
                  <td className="px-3 py-2 text-right font-mono">{m.on_hand_after}</td>
                  <td className="px-3 py-2 text-muted-foreground">{m.reference}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
