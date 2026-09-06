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
import type { BomComponentInput } from "@/lib/manufacturing/api";
import {
  useApproveBom,
  useBoms,
  useCanManageManufacturing,
  useCreateBom,
} from "@/lib/manufacturing/hooks";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "success" | "destructive"> = {
  draft: "secondary",
  active: "success",
  archived: "destructive",
};

/** BOMs (Phase P2.12) — list + create (with components) + approve. Approving a BOM activates
 * it for explosion and production-order release. Item ids are raw Inventory Item UUIDs. */
export function BomsPanel() {
  const boms = useBoms();
  const approve = useApproveBom();
  const canManage = useCanManageManufacturing();
  const [creating, setCreating] = useState(false);

  if (boms.isLoading) return <Skeleton className="h-48 w-full" />;
  if (boms.isError) return <ErrorState title="Couldn't load BOMs" />;

  const rows = boms.data ?? [];

  async function doApprove(id: string) {
    try {
      await approve.mutateAsync(id);
      toast.success("BOM approved");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not approve BOM");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Bills of materials</h2>
        {canManage && <Button size="sm" onClick={() => setCreating(true)}>New BOM</Button>}
      </div>
      {rows.length === 0 ? (
        <EmptyState
          title="No BOMs"
          description="Create a bill of materials with its components, then approve it to use in production."
          action={canManage ? { label: "New BOM", onClick: () => setCreating(true) } : undefined}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Number</th>
                <th className="px-3 py-2">Product item id</th>
                <th className="px-3 py-2 text-right">Qty</th>
                <th className="px-3 py-2">Rev</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((b) => (
                <tr key={b.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono">{b.number}</td>
                  <td className="px-3 py-2 font-mono text-xs">{b.product_item_id}</td>
                  <td className="px-3 py-2 text-right font-mono">{b.quantity}</td>
                  <td className="px-3 py-2">{b.revision}</td>
                  <td className="px-3 py-2">
                    <Badge variant={STATUS_VARIANT[b.status] ?? "secondary"}>{b.status}</Badge>
                  </td>
                  <td className="px-3 py-2 text-right">
                    {canManage && b.status !== "active" && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={approve.isPending}
                        onClick={() => doApprove(b.id)}
                      >
                        Approve
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {creating && <BomDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

function BomDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateBom();
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [revision, setRevision] = useState("A");
  const [components, setComponents] = useState<BomComponentInput[]>([
    { component_item_id: "", quantity: "1", scrap_percent: "0" },
  ]);

  function updateComponent(i: number, patch: Partial<BomComponentInput>) {
    setComponents((cs) => cs.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  }
  function addComponent() {
    setComponents((cs) => [...cs, { component_item_id: "", quantity: "1", scrap_percent: "0" }]);
  }
  function removeComponent(i: number) {
    setComponents((cs) => (cs.length === 1 ? cs : cs.filter((_, idx) => idx !== i)));
  }

  const validComponents = components.filter((c) => c.component_item_id.trim());

  async function save() {
    try {
      await create.mutateAsync({
        product_item_id: productId.trim(),
        quantity: quantity.trim() || "1",
        revision: revision.trim() || "A",
        components: validComponents.map((c) => ({
          component_item_id: c.component_item_id.trim(),
          quantity: c.quantity.trim() || "1",
          scrap_percent: (c.scrap_percent ?? "0").trim() || "0",
        })),
      });
      toast.success("BOM created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create BOM");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New bill of materials</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="flex-1 min-w-[16rem]">
              <Label htmlFor="bom-product">Product item id</Label>
              <Input
                id="bom-product"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                placeholder="Inventory Item UUID"
              />
            </div>
            <div className="w-28">
              <Label htmlFor="bom-qty">Quantity</Label>
              <Input id="bom-qty" value={quantity} onChange={(e) => setQuantity(e.target.value)} inputMode="decimal" />
            </div>
            <div className="w-24">
              <Label htmlFor="bom-rev">Revision</Label>
              <Input id="bom-rev" value={revision} onChange={(e) => setRevision(e.target.value)} />
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <Label>Components</Label>
              <Button type="button" size="sm" variant="outline" onClick={addComponent}>
                Add component
              </Button>
            </div>
            <div className="space-y-2">
              {components.map((c, i) => (
                <div key={i} className="flex flex-wrap items-end gap-2">
                  <div className="flex-1 min-w-[14rem]">
                    <Label htmlFor={`cmp-item-${i}`} className="text-xs">Component item id</Label>
                    <Input
                      id={`cmp-item-${i}`}
                      value={c.component_item_id}
                      onChange={(e) => updateComponent(i, { component_item_id: e.target.value })}
                      placeholder="Inventory Item UUID"
                    />
                  </div>
                  <div className="w-24">
                    <Label htmlFor={`cmp-qty-${i}`} className="text-xs">Qty</Label>
                    <Input
                      id={`cmp-qty-${i}`}
                      value={c.quantity}
                      onChange={(e) => updateComponent(i, { quantity: e.target.value })}
                      inputMode="decimal"
                    />
                  </div>
                  <div className="w-24">
                    <Label htmlFor={`cmp-scrap-${i}`} className="text-xs">Scrap %</Label>
                    <Input
                      id={`cmp-scrap-${i}`}
                      value={c.scrap_percent ?? "0"}
                      onChange={(e) => updateComponent(i, { scrap_percent: e.target.value })}
                      inputMode="decimal"
                    />
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => removeComponent(i)}
                    disabled={components.length === 1}
                    aria-label={`Remove component ${i + 1}`}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            onClick={save}
            disabled={create.isPending || !productId.trim() || validComponents.length === 0}
          >
            {create.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
