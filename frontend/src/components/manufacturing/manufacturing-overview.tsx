"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import {
  useCanManageManufacturing,
  useExplodeBom,
  useRunSetup,
} from "@/lib/manufacturing/hooks";

/**
 * Manufacturing overview (Phase P2.12) — the admin-only "Run setup" action that ensures
 * BOM-/MO- numbering, plus a multi-level BOM explosion preview. BOM explosion and the
 * whole order lifecycle (release → issue → complete) run server-side.
 */
export function ManufacturingOverview() {
  const setup = useRunSetup();
  const canManage = useCanManageManufacturing();

  async function doSetup() {
    try {
      const res = await setup.mutateAsync();
      toast.success(res.detail || "Manufacturing setup complete");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not run setup");
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-medium">Setup</h2>
            <p className="text-sm text-muted-foreground">
              Ensures BOM and manufacturing-order numbering sequences exist.
            </p>
          </div>
          {canManage && (
            <Button size="sm" onClick={doSetup} disabled={setup.isPending}>
              {setup.isPending ? "Running…" : "Run setup"}
            </Button>
          )}
        </div>
      </div>

      <BomExplodePreview />
    </div>
  );
}

/** Multi-level BOM explosion preview — product id + quantity → flat component requirements. */
export function BomExplodePreview() {
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [active, setActive] = useState<{ productId: string; quantity: string } | null>(null);

  const explode = useExplodeBom(active?.productId, active?.quantity ?? "");

  const requirements = explode.data?.requirements ?? {};
  const entries = Object.entries(requirements);

  return (
    <div className="rounded-lg border p-4">
      <h2 className="text-lg font-medium">BOM explosion preview</h2>
      <p className="text-sm text-muted-foreground">
        Enter a product item id (raw Inventory Item UUID — no picker yet) and quantity to see the
        full multi-level component requirements.
      </p>
      <form
        className="mt-3 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (productId.trim()) setActive({ productId: productId.trim(), quantity: quantity.trim() || "1" });
        }}
      >
        <div className="flex-1 min-w-[16rem]">
          <Label htmlFor="ex-product">Product item id</Label>
          <Input
            id="ex-product"
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
          />
        </div>
        <div className="w-28">
          <Label htmlFor="ex-qty">Quantity</Label>
          <Input id="ex-qty" value={quantity} onChange={(e) => setQuantity(e.target.value)} inputMode="decimal" />
        </div>
        <Button type="submit" disabled={!productId.trim()}>
          Explode
        </Button>
      </form>

      {active && (
        <div className="mt-4">
          {explode.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : explode.isError ? (
            <p className="rounded-md border p-3 text-sm text-destructive">Couldn&apos;t explode this BOM.</p>
          ) : entries.length === 0 ? (
            <p className="rounded-md border p-3 text-sm text-muted-foreground">
              No requirements — this product may have no active BOM.
            </p>
          ) : (
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm">
                <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2">Component item id</th>
                    <th className="px-3 py-2 text-right">Required qty</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map(([itemId, qty]) => (
                    <tr key={itemId} className="border-b last:border-0">
                      <td className="px-3 py-2 font-mono text-xs">{itemId}</td>
                      <td className="px-3 py-2 text-right font-mono">{qty}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
