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
import type { ProductionOrder } from "@/lib/manufacturing/api";
import {
  useCanManageManufacturing,
  useCreateOrder,
  useOrders,
} from "@/lib/manufacturing/hooks";

import { OrderLifecycle } from "./order-lifecycle";

export const ORDER_STATUS_VARIANT: Record<string, "default" | "secondary" | "success" | "destructive"> = {
  draft: "secondary",
  planned: "secondary",
  released: "default",
  in_progress: "default",
  completed: "success",
  closed: "success",
  cancelled: "destructive",
};

/** Production orders (Phase P2.12) — list + create, with a selected order's full lifecycle. */
export function OrdersPanel() {
  const orders = useOrders();
  const canManage = useCanManageManufacturing();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  if (orders.isError) return <ErrorState title="Couldn't load production orders" />;

  const rows = orders.data ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Production orders</h2>
          {canManage && <Button size="sm" onClick={() => setCreating(true)}>New order</Button>}
        </div>
        {orders.isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No production orders"
            description="Create a manufacturing order from a product, BOM and routing."
            action={canManage ? { label: "New order", onClick: () => setCreating(true) } : undefined}
          />
        ) : (
          <ul className="space-y-1">
            {rows.map((o) => (
              <li key={o.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(o.id)}
                  className={`flex w-full items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-accent ${
                    o.id === selectedId ? "border-primary bg-primary/5" : ""
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-xs">{o.number}</span>
                    <Badge variant={ORDER_STATUS_VARIANT[o.status] ?? "secondary"}>{o.status}</Badge>
                  </span>
                  <span className="font-mono text-muted-foreground">{o.quantity}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        {selectedId ? (
          <OrderLifecycle orderId={selectedId} />
        ) : (
          <EmptyState
            title="No order selected"
            description="Select a production order to drive its release → issue → complete → close lifecycle."
          />
        )}
      </div>
      {creating && <OrderDialog onClose={() => setCreating(false)} onCreated={(id) => setSelectedId(id)} />}
    </div>
  );
}

function OrderDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const create = useCreateOrder();
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [bomId, setBomId] = useState("");
  const [routingId, setRoutingId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");

  async function save() {
    try {
      const order: ProductionOrder = await create.mutateAsync({
        product_item_id: productId.trim(),
        quantity: quantity.trim() || "1",
        bom_id: bomId.trim() || undefined,
        routing_id: routingId.trim() || undefined,
        warehouse_id: warehouseId.trim() || undefined,
      });
      toast.success("Production order created");
      onCreated(order.id);
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create order");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New production order</DialogTitle>
        </DialogHeader>
        <p className="text-xs text-muted-foreground">
          Product, BOM, routing and warehouse are referenced by raw id (no picker yet).
        </p>
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="ord-product">Product item id</Label>
              <Input id="ord-product" value={productId} onChange={(e) => setProductId(e.target.value)} placeholder="Inventory Item UUID" />
            </div>
            <div className="w-28">
              <Label htmlFor="ord-qty">Quantity</Label>
              <Input id="ord-qty" value={quantity} onChange={(e) => setQuantity(e.target.value)} inputMode="decimal" />
            </div>
          </div>
          <div>
            <Label htmlFor="ord-bom">BOM id</Label>
            <Input id="ord-bom" value={bomId} onChange={(e) => setBomId(e.target.value)} placeholder="(optional)" />
          </div>
          <div>
            <Label htmlFor="ord-routing">Routing id</Label>
            <Input id="ord-routing" value={routingId} onChange={(e) => setRoutingId(e.target.value)} placeholder="(optional)" />
          </div>
          <div>
            <Label htmlFor="ord-wh">Warehouse id</Label>
            <Input id="ord-wh" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} placeholder="(optional)" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={create.isPending || !productId.trim()}>
            {create.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
