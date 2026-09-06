"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useStandardCost } from "@/lib/manufacturing/hooks";

/** Standard cost calculator (Phase P2.12) — material + labor + machine + overhead = total,
 * computed server-side from the active BOM and the supplied labor inputs. */
export function StandardCostPanel() {
  const [productId, setProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [laborMinutes, setLaborMinutes] = useState("");
  const [laborRate, setLaborRate] = useState("");
  const [overhead, setOverhead] = useState("");
  const [params, setParams] = useState<{
    product_item_id: string;
    quantity: string;
    labor_minutes?: string;
    labor_rate_per_hour?: string;
    overhead_percent?: string;
  } | null>(null);

  const cost = useStandardCost(params);

  return (
    <div className="rounded-lg border p-4">
      <h2 className="text-lg font-medium">Standard cost calculator</h2>
      <p className="text-sm text-muted-foreground">
        Roll up the standard cost for a product (raw Inventory Item id) at a given quantity.
      </p>
      <form
        className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (productId.trim())
            setParams({
              product_item_id: productId.trim(),
              quantity: quantity.trim() || "1",
              labor_minutes: laborMinutes.trim() || undefined,
              labor_rate_per_hour: laborRate.trim() || undefined,
              overhead_percent: overhead.trim() || undefined,
            });
        }}
      >
        <div className="sm:col-span-2 lg:col-span-1">
          <Label htmlFor="sc-product">Product item id</Label>
          <Input id="sc-product" value={productId} onChange={(e) => setProductId(e.target.value)} placeholder="Inventory Item UUID" />
        </div>
        <div>
          <Label htmlFor="sc-qty">Quantity</Label>
          <Input id="sc-qty" value={quantity} onChange={(e) => setQuantity(e.target.value)} inputMode="decimal" />
        </div>
        <div>
          <Label htmlFor="sc-labmin">Labor minutes</Label>
          <Input id="sc-labmin" value={laborMinutes} onChange={(e) => setLaborMinutes(e.target.value)} inputMode="decimal" />
        </div>
        <div>
          <Label htmlFor="sc-labrate">Labor rate/hr</Label>
          <Input id="sc-labrate" value={laborRate} onChange={(e) => setLaborRate(e.target.value)} inputMode="decimal" />
        </div>
        <div>
          <Label htmlFor="sc-ovh">Overhead %</Label>
          <Input id="sc-ovh" value={overhead} onChange={(e) => setOverhead(e.target.value)} inputMode="decimal" />
        </div>
        <div className="flex items-end">
          <Button type="submit" disabled={!productId.trim()}>Calculate</Button>
        </div>
      </form>

      {params && (
        <div className="mt-4">
          {cost.isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : cost.isError ? (
            <p className="rounded-md border p-3 text-sm text-destructive">Couldn&apos;t compute the standard cost.</p>
          ) : cost.data ? (
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <CostStat label="Material" value={cost.data.material} />
              <CostStat label="Labor" value={cost.data.labor} />
              <CostStat label="Machine" value={cost.data.machine} />
              <CostStat label="Overhead" value={cost.data.overhead} />
              <CostStat label="Total" value={cost.data.total} emphasis />
            </dl>
          ) : null}
        </div>
      )}
    </div>
  );
}

function CostStat({ label, value, emphasis }: { label: string; value: string; emphasis?: boolean }) {
  return (
    <div className="rounded-lg border p-3">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className={emphasis ? "font-mono text-lg font-semibold text-primary" : "font-mono text-lg font-medium"}>{value}</dd>
    </div>
  );
}
