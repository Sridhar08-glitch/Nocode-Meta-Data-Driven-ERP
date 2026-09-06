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
import type { Item, ValuationMethod } from "@/lib/inventory/api";
import { useCreateItem, useDeleteItem, useItems } from "@/lib/inventory/hooks";

const METHODS: { value: ValuationMethod; label: string }[] = [
  { value: "average", label: "Weighted average" },
  { value: "fifo", label: "FIFO" },
  { value: "standard", label: "Standard cost" },
];

/** Item master (Phase P2.4) — list + create/delete. Costing method is fixed per item
 * because changing it mid-stream would invalidate the cost ledger. */
export function ItemsPanel() {
  const items = useItems();
  const del = useDeleteItem();
  const [creating, setCreating] = useState(false);

  const rows = items.data ?? [];

  async function doDelete(it: Item) {
    try {
      await del.mutateAsync(it.id);
      toast.success("Item deleted");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Item has stock movements — deactivate instead");
    }
  }

  if (items.isLoading) return <Skeleton className="h-64 w-full" />;
  if (items.isError) return <ErrorState title="Couldn't load items" />;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setCreating(true)}>New item</Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No items"
          description="Create your first stock item to start receiving and issuing inventory."
          action={{ label: "New item", onClick: () => setCreating(true) }} />
      ) : (
        <ul className="space-y-1">
          {rows.map((it) => (
            <li key={it.id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-mono text-muted-foreground">{it.sku}</span>
                <span>{it.name}</span>
                <Badge variant="secondary">{it.valuation_method}</Badge>
                {!it.is_active && <Badge variant="destructive">inactive</Badge>}
              </span>
              <span className="flex items-center gap-2">
                <span className="text-muted-foreground">{it.uom}</span>
                <Button variant="ghost" size="sm" aria-label={`Delete ${it.sku}`}
                  onClick={() => doDelete(it)} disabled={del.isPending}>Delete</Button>
              </span>
            </li>
          ))}
        </ul>
      )}
      {creating && <ItemDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

function ItemDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateItem();
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [uom, setUom] = useState("ea");
  const [method, setMethod] = useState<ValuationMethod>("average");
  const [standardCost, setStandardCost] = useState("0");
  const [invAcct, setInvAcct] = useState("");
  const [cogsAcct, setCogsAcct] = useState("");

  async function save() {
    try {
      await create.mutateAsync({
        sku: sku.trim(), name: name.trim(), uom: uom.trim() || "ea", valuation_method: method,
        standard_cost: standardCost.trim() || "0",
        inventory_account_code: invAcct.trim(), cogs_account_code: cogsAcct.trim(),
      });
      toast.success("Item created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create item");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New item</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="w-40">
              <Label htmlFor="item-sku">SKU</Label>
              <Input id="item-sku" value={sku} onChange={(e) => setSku(e.target.value)} placeholder="WIDGET-01" />
            </div>
            <div className="flex-1">
              <Label htmlFor="item-name">Name</Label>
              <Input id="item-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Blue widget" />
            </div>
          </div>
          <div className="flex gap-3">
            <div className="w-24">
              <Label htmlFor="item-uom">Unit</Label>
              <Input id="item-uom" value={uom} onChange={(e) => setUom(e.target.value)} placeholder="ea" />
            </div>
            <div className="flex-1">
              <Label htmlFor="item-method">Valuation</Label>
              <Select value={method} onValueChange={(v) => setMethod(v as ValuationMethod)}>
                <SelectTrigger id="item-method" aria-label="Valuation method"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {METHODS.map((m) => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="w-32">
              <Label htmlFor="item-std">Standard cost</Label>
              <Input id="item-std" value={standardCost} onChange={(e) => setStandardCost(e.target.value)} inputMode="decimal" />
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="item-inv-acct">Inventory account code</Label>
              <Input id="item-inv-acct" value={invAcct} onChange={(e) => setInvAcct(e.target.value)} placeholder="1300" />
            </div>
            <div className="flex-1">
              <Label htmlFor="item-cogs-acct">COGS account code</Label>
              <Input id="item-cogs-acct" value={cogsAcct} onChange={(e) => setCogsAcct(e.target.value)} placeholder="5000" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={create.isPending || !sku.trim() || !name.trim()}>
            {create.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
