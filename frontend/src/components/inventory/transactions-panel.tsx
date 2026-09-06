"use client";

import { useState } from "react";

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
import { EmptyState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useAdjust, useIssue, useItems, useReceive, useTransfer, useWarehouses } from "@/lib/inventory/hooks";

type TxnType = "receive" | "issue" | "adjust" | "transfer";

const TABS: { value: TxnType; label: string }[] = [
  { value: "receive", label: "Receive" },
  { value: "issue", label: "Issue" },
  { value: "adjust", label: "Adjust" },
  { value: "transfer", label: "Transfer" },
];

/** Stock transactions (Phase P2.4) — post receive/issue/adjust/transfer movements. Costing
 * (FIFO / weighted-average) and the race-safe stock math run server-side. */
export function TransactionsPanel() {
  const [tab, setTab] = useState<TxnType>("receive");
  const items = useItems();
  const warehouses = useWarehouses();

  const itemRows = items.data ?? [];
  const whRows = warehouses.data ?? [];

  if (itemRows.length === 0 || whRows.length === 0) {
    return (
      <EmptyState title="Set up master data first"
        description="Create at least one item and one warehouse before posting stock transactions." />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1" role="tablist" aria-label="Transaction type">
        {TABS.map((t) => (
          <Button key={t.value} role="tab" aria-selected={tab === t.value}
            variant={tab === t.value ? "default" : "outline"} size="sm"
            onClick={() => setTab(t.value)}>{t.label}</Button>
        ))}
      </div>
      <TxnForm
        type={tab}
        items={itemRows.map((i) => ({ id: i.id, label: `${i.sku} — ${i.name}` }))}
        warehouses={whRows.map((w) => ({ id: w.id, label: `${w.code} — ${w.name}` }))}
      />
    </div>
  );
}

type Opt = { id: string; label: string };

function TxnForm({ type, items, warehouses }: { type: TxnType; items: Opt[]; warehouses: Opt[] }) {
  const receive = useReceive();
  const issue = useIssue();
  const adjust = useAdjust();
  const transfer = useTransfer();

  const [item, setItem] = useState(items[0]?.id ?? "");
  const [warehouse, setWarehouse] = useState(warehouses[0]?.id ?? "");
  const [toWarehouse, setToWarehouse] = useState(warehouses[1]?.id ?? warehouses[0]?.id ?? "");
  const [quantity, setQuantity] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [reference, setReference] = useState("");

  const pending = receive.isPending || issue.isPending || adjust.isPending || transfer.isPending;
  const qtyLabel = type === "adjust" ? "Quantity delta (±)" : "Quantity";

  function reset() {
    setQuantity("");
    setUnitCost("");
    setReference("");
  }

  async function submit() {
    const qty = quantity.trim();
    if (!item || !warehouse || !qty) {
      toast.error("Item, warehouse and quantity are required");
      return;
    }
    try {
      if (type === "receive") {
        await receive.mutateAsync({ item, warehouse, quantity: qty, unit_cost: unitCost.trim() || "0", reference: reference.trim() });
      } else if (type === "issue") {
        await issue.mutateAsync({ item, warehouse, quantity: qty, reference: reference.trim() });
      } else if (type === "adjust") {
        await adjust.mutateAsync({ item, warehouse, quantity_delta: qty, unit_cost: unitCost.trim() || undefined, reference: reference.trim() });
      } else {
        if (warehouse === toWarehouse) {
          toast.error("Source and destination warehouses must differ");
          return;
        }
        await transfer.mutateAsync({ item, from_warehouse: warehouse, to_warehouse: toWarehouse, quantity: qty, reference: reference.trim() });
      }
      toast.success(`${type[0].toUpperCase()}${type.slice(1)} posted`);
      reset();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not post transaction");
    }
  }

  return (
    <div className="max-w-xl space-y-3 rounded-lg border p-4">
      <div>
        <Label htmlFor="txn-item">Item</Label>
        <Select value={item} onValueChange={setItem}>
          <SelectTrigger id="txn-item" aria-label="Item"><SelectValue /></SelectTrigger>
          <SelectContent>
            {items.map((o) => <SelectItem key={o.id} value={o.id}>{o.label}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      <div className="flex gap-3">
        <div className="flex-1">
          <Label htmlFor="txn-wh">{type === "transfer" ? "From warehouse" : "Warehouse"}</Label>
          <Select value={warehouse} onValueChange={setWarehouse}>
            <SelectTrigger id="txn-wh" aria-label="Warehouse"><SelectValue /></SelectTrigger>
            <SelectContent>
              {warehouses.map((o) => <SelectItem key={o.id} value={o.id}>{o.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        {type === "transfer" && (
          <div className="flex-1">
            <Label htmlFor="txn-to-wh">To warehouse</Label>
            <Select value={toWarehouse} onValueChange={setToWarehouse}>
              <SelectTrigger id="txn-to-wh" aria-label="Destination warehouse"><SelectValue /></SelectTrigger>
              <SelectContent>
                {warehouses.map((o) => <SelectItem key={o.id} value={o.id}>{o.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <div className="flex-1">
          <Label htmlFor="txn-qty">{qtyLabel}</Label>
          <Input id="txn-qty" value={quantity} onChange={(e) => setQuantity(e.target.value)} inputMode="decimal" placeholder={type === "adjust" ? "-5" : "10"} />
        </div>
        {(type === "receive" || type === "adjust") && (
          <div className="flex-1">
            <Label htmlFor="txn-cost">Unit cost</Label>
            <Input id="txn-cost" value={unitCost} onChange={(e) => setUnitCost(e.target.value)} inputMode="decimal" placeholder="2.50" />
          </div>
        )}
      </div>

      <div>
        <Label htmlFor="txn-ref">Reference</Label>
        <Input id="txn-ref" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="PO-1001" />
      </div>

      <div className="flex justify-end">
        <Button onClick={submit} disabled={pending}>{pending ? "Posting…" : `Post ${type}`}</Button>
      </div>
    </div>
  );
}
