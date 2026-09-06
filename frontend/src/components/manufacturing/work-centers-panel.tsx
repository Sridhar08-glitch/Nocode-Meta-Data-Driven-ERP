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
import type { CenterType } from "@/lib/manufacturing/api";
import {
  useCanManageManufacturing,
  useCreateWorkCenter,
  useWorkCenters,
} from "@/lib/manufacturing/hooks";

const TYPES: { value: CenterType; label: string }[] = [
  { value: "labor", label: "Labor" },
  { value: "machine", label: "Machine" },
  { value: "hybrid", label: "Hybrid" },
];

/** Work centers (Phase P2.12) — list + create. Each center carries capacity, efficiency and
 * an hourly cost used in routing-step time and labor/overhead costing. */
export function WorkCentersPanel() {
  const centers = useWorkCenters();
  const canManage = useCanManageManufacturing();
  const [creating, setCreating] = useState(false);

  if (centers.isLoading) return <Skeleton className="h-48 w-full" />;
  if (centers.isError) return <ErrorState title="Couldn't load work centers" />;

  const rows = centers.data ?? [];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Work centers</h2>
        {canManage && <Button size="sm" onClick={() => setCreating(true)}>New work center</Button>}
      </div>
      {rows.length === 0 ? (
        <EmptyState
          title="No work centers"
          description="Create a labor or machine center used by routings and operations."
          action={canManage ? { label: "New work center", onClick: () => setCreating(true) } : undefined}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2 text-right">Capacity/hr</th>
                <th className="px-3 py-2 text-right">Efficiency</th>
                <th className="px-3 py-2 text-right">Cost/hr</th>
                <th className="px-3 py-2">Active</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono">{c.code}</td>
                  <td className="px-3 py-2">{c.name}</td>
                  <td className="px-3 py-2">
                    <Badge variant="secondary">{c.center_type}</Badge>
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{c.capacity_per_hour}</td>
                  <td className="px-3 py-2 text-right font-mono">{c.efficiency}</td>
                  <td className="px-3 py-2 text-right font-mono">{c.cost_per_hour}</td>
                  <td className="px-3 py-2">{c.is_active ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {creating && <WorkCenterDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

function WorkCenterDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateWorkCenter();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [centerType, setCenterType] = useState<CenterType>("labor");
  const [capacity, setCapacity] = useState("1");
  const [efficiency, setEfficiency] = useState("1");
  const [cost, setCost] = useState("0");

  async function save() {
    try {
      await create.mutateAsync({
        code: code.trim(),
        name: name.trim(),
        center_type: centerType,
        capacity_per_hour: capacity.trim() || "1",
        efficiency: efficiency.trim() || "1",
        cost_per_hour: cost.trim() || "0",
      });
      toast.success("Work center created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create work center");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New work center</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="w-32">
              <Label htmlFor="wc-code">Code</Label>
              <Input id="wc-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="WC-01" />
            </div>
            <div className="flex-1">
              <Label htmlFor="wc-name">Name</Label>
              <Input id="wc-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Assembly line" />
            </div>
          </div>
          <div>
            <Label htmlFor="wc-type">Type</Label>
            <Select value={centerType} onValueChange={(v) => setCenterType(v as CenterType)}>
              <SelectTrigger id="wc-type" aria-label="Center type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="wc-cap">Capacity/hr</Label>
              <Input id="wc-cap" value={capacity} onChange={(e) => setCapacity(e.target.value)} inputMode="decimal" />
            </div>
            <div className="flex-1">
              <Label htmlFor="wc-eff">Efficiency</Label>
              <Input id="wc-eff" value={efficiency} onChange={(e) => setEfficiency(e.target.value)} inputMode="decimal" />
            </div>
            <div className="flex-1">
              <Label htmlFor="wc-cost">Cost/hr</Label>
              <Input id="wc-cost" value={cost} onChange={(e) => setCost(e.target.value)} inputMode="decimal" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={create.isPending || !code.trim() || !name.trim()}>
            {create.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
