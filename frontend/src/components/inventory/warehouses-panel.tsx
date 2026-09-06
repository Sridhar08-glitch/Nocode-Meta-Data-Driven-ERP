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
import type { Warehouse } from "@/lib/inventory/api";
import { useCreateWarehouse, useDeleteWarehouse, useWarehouses } from "@/lib/inventory/hooks";

/** Warehouse master (Phase P2.4) — stocking locations that hold per-item balances. */
export function WarehousesPanel() {
  const warehouses = useWarehouses();
  const del = useDeleteWarehouse();
  const [creating, setCreating] = useState(false);

  const rows = warehouses.data ?? [];

  async function doDelete(w: Warehouse) {
    try {
      await del.mutateAsync(w.id);
      toast.success("Warehouse deleted");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Warehouse holds stock — deactivate instead");
    }
  }

  if (warehouses.isLoading) return <Skeleton className="h-64 w-full" />;
  if (warehouses.isError) return <ErrorState title="Couldn't load warehouses" />;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button onClick={() => setCreating(true)}>New warehouse</Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No warehouses"
          description="Add a warehouse before receiving stock — every movement is posted against one."
          action={{ label: "New warehouse", onClick: () => setCreating(true) }} />
      ) : (
        <ul className="space-y-1">
          {rows.map((w) => (
            <li key={w.id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-mono text-muted-foreground">{w.code}</span>
                <span>{w.name}</span>
                {!w.is_active && <Badge variant="destructive">inactive</Badge>}
              </span>
              <Button variant="ghost" size="sm" aria-label={`Delete ${w.code}`}
                onClick={() => doDelete(w)} disabled={del.isPending}>Delete</Button>
            </li>
          ))}
        </ul>
      )}
      {creating && <WarehouseDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

function WarehouseDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateWarehouse();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");

  async function save() {
    try {
      await create.mutateAsync({ code: code.trim(), name: name.trim() });
      toast.success("Warehouse created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create warehouse");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New warehouse</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="w-32">
              <Label htmlFor="wh-code">Code</Label>
              <Input id="wh-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="MAIN" />
            </div>
            <div className="flex-1">
              <Label htmlFor="wh-name">Name</Label>
              <Input id="wh-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Main warehouse" />
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
