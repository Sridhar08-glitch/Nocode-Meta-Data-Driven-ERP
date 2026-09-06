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
import { ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { Operation, OrderStatus } from "@/lib/manufacturing/api";
import {
  useCanManageManufacturing,
  useCloseOrder,
  useCompleteOperation,
  useCompleteOrder,
  useIssueOrder,
  useOperations,
  useOrderOee,
  useOrders,
  useReleaseOrder,
  useReservations,
} from "@/lib/manufacturing/hooks";

import { ORDER_STATUS_VARIANT } from "./orders-panel";

/**
 * Production order lifecycle (Phase P2.12) — drives the server state machine
 * draft/planned → (release: explode BOM → reservations + operations) → released →
 * (issue: consume inventory → WIP) → in_progress → (complete: FG receipt + GL + cost
 * rollup) → completed → (close) → closed. Each action is enabled only from a valid state;
 * the server enforces the real transitions and surfaces 400 messages via toast.
 */
export function OrderLifecycle({ orderId }: { orderId: string }) {
  const orders = useOrders();
  const reservations = useReservations(orderId);
  const operations = useOperations(orderId);
  const canManage = useCanManageManufacturing();

  const release = useReleaseOrder();
  const issue = useIssueOrder();
  const close = useCloseOrder();
  const complete = useCompleteOrder();

  const [completing, setCompleting] = useState(false);

  const order = (orders.data ?? []).find((o) => o.id === orderId);

  if (orders.isLoading) return <Skeleton className="h-64 w-full" />;
  if (orders.isError || !order) return <ErrorState title="Couldn't load order" />;

  const status = order.status as OrderStatus;
  const pending = release.isPending || issue.isPending || close.isPending || complete.isPending;
  const canComplete = status === "released" || status === "in_progress";
  const oeeVisible = status === "completed" || status === "closed";

  async function act(label: string, fn: () => Promise<unknown>) {
    try {
      await fn();
      toast.success(label);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Action failed");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm">{order.number}</span>
          <Badge variant={ORDER_STATUS_VARIANT[status] ?? "secondary"}>{status}</Badge>
        </div>
        {canManage && (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={pending || !(status === "draft" || status === "planned")}
              onClick={() => act("Order released", () => release.mutateAsync(orderId))}
            >
              Release
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={pending || status !== "released"}
              onClick={() => act("Materials issued", () => issue.mutateAsync(orderId))}
            >
              Issue
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={pending || !canComplete}
              onClick={() => setCompleting(true)}
            >
              Complete
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={pending || status !== "completed"}
              onClick={() => act("Order closed", () => close.mutateAsync(orderId))}
            >
              Close
            </Button>
          </div>
        )}
      </div>

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="Quantity" value={order.quantity} />
        <Stat label="Material" value={order.material_cost} />
        <Stat label="Labor" value={order.labor_cost} />
        <Stat label="Overhead" value={order.overhead_cost} />
        <Stat label="Total cost" value={order.total_cost} />
      </dl>

      {oeeVisible && <OeeDisplay orderId={orderId} />}

      <ReservationsList orderId={orderId} loading={reservations.isLoading} rows={reservations.data ?? []} />

      <OperationsList
        orderId={orderId}
        loading={operations.isLoading}
        rows={operations.data ?? []}
        canManage={canManage}
      />

      {completing && (
        <CompleteDialog
          onClose={() => setCompleting(false)}
          onSubmit={async (vars) => {
            await act("Order completed", () => complete.mutateAsync({ id: orderId, ...vars }));
            setCompleting(false);
          }}
          pending={complete.isPending}
          defaultQty={order.quantity}
        />
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border p-3">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="font-mono text-lg font-medium">{value}</dd>
    </div>
  );
}

function OeeDisplay({ orderId }: { orderId: string }) {
  const oee = useOrderOee(orderId);
  if (oee.isLoading) return <Skeleton className="h-20 w-full" />;
  if (oee.isError || !oee.data) return null;
  return (
    <div className="rounded-lg border p-4">
      <h3 className="mb-2 text-sm font-medium">Overall equipment effectiveness (OEE)</h3>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Availability" value={oee.data.availability} />
        <Stat label="Performance" value={oee.data.performance} />
        <Stat label="Quality" value={oee.data.quality} />
        <Stat label="OEE" value={oee.data.oee} />
      </dl>
    </div>
  );
}

function ReservationsList({
  loading,
  rows,
}: {
  orderId: string;
  loading: boolean;
  rows: { id: string; component_item_id: string; quantity: string; status: string }[];
}) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium">Material reservations</h3>
      {loading ? (
        <Skeleton className="h-20 w-full" />
      ) : rows.length === 0 ? (
        <p className="rounded-md border p-4 text-sm text-muted-foreground">
          No reservations yet — release the order to explode the BOM into reservations.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Component item id</th>
                <th className="px-3 py-2 text-right">Quantity</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">{r.component_item_id}</td>
                  <td className="px-3 py-2 text-right font-mono">{r.quantity}</td>
                  <td className="px-3 py-2">{r.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function OperationsList({
  orderId,
  loading,
  rows,
  canManage,
}: {
  orderId: string;
  loading: boolean;
  rows: Operation[];
  canManage: boolean;
}) {
  const [completingId, setCompletingId] = useState<string | null>(null);
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium">Operations</h3>
      {loading ? (
        <Skeleton className="h-20 w-full" />
      ) : rows.length === 0 ? (
        <p className="rounded-md border p-4 text-sm text-muted-foreground">
          No operations yet — released orders with a routing generate operations.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Seq</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">Good</th>
                <th className="px-3 py-2 text-right">Reject</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows
                .slice()
                .sort((a, b) => a.sequence - b.sequence)
                .map((op) => (
                  <tr key={op.id} className="border-b last:border-0">
                    <td className="px-3 py-2 text-muted-foreground">{op.sequence}</td>
                    <td className="px-3 py-2">{op.name}</td>
                    <td className="px-3 py-2">
                      <Badge variant={op.status === "completed" ? "success" : "secondary"}>{op.status}</Badge>
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{op.good_qty}</td>
                    <td className="px-3 py-2 text-right font-mono">{op.reject_qty}</td>
                    <td className="px-3 py-2 text-right">
                      {canManage && op.status !== "completed" && (
                        <Button size="sm" variant="outline" onClick={() => setCompletingId(op.id)}>
                          Complete
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
      {completingId && (
        <CompleteOperationDialog
          orderId={orderId}
          operationId={completingId}
          onClose={() => setCompletingId(null)}
        />
      )}
    </div>
  );
}

function CompleteDialog({
  onClose,
  onSubmit,
  pending,
  defaultQty,
}: {
  onClose: () => void;
  onSubmit: (vars: { good_qty: string; overhead_percent?: string; lot_number?: string }) => Promise<void>;
  pending: boolean;
  defaultQty: string;
}) {
  const [goodQty, setGoodQty] = useState(defaultQty);
  const [overhead, setOverhead] = useState("");
  const [lot, setLot] = useState("");

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Complete production order</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="cmp-good">Good quantity</Label>
            <Input id="cmp-good" value={goodQty} onChange={(e) => setGoodQty(e.target.value)} inputMode="decimal" />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="cmp-ovh">Overhead %</Label>
              <Input id="cmp-ovh" value={overhead} onChange={(e) => setOverhead(e.target.value)} inputMode="decimal" placeholder="(optional)" />
            </div>
            <div className="flex-1">
              <Label htmlFor="cmp-lot">Lot number</Label>
              <Input id="cmp-lot" value={lot} onChange={(e) => setLot(e.target.value)} placeholder="(optional)" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button
            disabled={pending || !goodQty.trim()}
            onClick={() =>
              onSubmit({
                good_qty: goodQty.trim(),
                overhead_percent: overhead.trim() || undefined,
                lot_number: lot.trim() || undefined,
              })
            }
          >
            {pending ? "Completing…" : "Complete"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CompleteOperationDialog({
  orderId,
  operationId,
  onClose,
}: {
  orderId: string;
  operationId: string;
  onClose: () => void;
}) {
  const complete = useCompleteOperation(orderId);
  const [laborMinutes, setLaborMinutes] = useState("0");
  const [machineMinutes, setMachineMinutes] = useState("0");
  const [downtimeMinutes, setDowntimeMinutes] = useState("0");
  const [goodQty, setGoodQty] = useState("0");
  const [rejectQty, setRejectQty] = useState("0");

  async function save() {
    try {
      await complete.mutateAsync({
        id: operationId,
        labor_minutes: laborMinutes.trim() || "0",
        machine_minutes: machineMinutes.trim() || "0",
        downtime_minutes: downtimeMinutes.trim() || "0",
        good_qty: goodQty.trim() || "0",
        reject_qty: rejectQty.trim() || "0",
      });
      toast.success("Operation completed");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not complete operation");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Complete operation</DialogTitle>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor="op-labor">Labor minutes</Label>
            <Input id="op-labor" value={laborMinutes} onChange={(e) => setLaborMinutes(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <Label htmlFor="op-machine">Machine minutes</Label>
            <Input id="op-machine" value={machineMinutes} onChange={(e) => setMachineMinutes(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <Label htmlFor="op-downtime">Downtime minutes</Label>
            <Input id="op-downtime" value={downtimeMinutes} onChange={(e) => setDowntimeMinutes(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <Label htmlFor="op-good">Good qty</Label>
            <Input id="op-good" value={goodQty} onChange={(e) => setGoodQty(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <Label htmlFor="op-reject">Reject qty</Label>
            <Input id="op-reject" value={rejectQty} onChange={(e) => setRejectQty(e.target.value)} inputMode="decimal" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={complete.isPending}>
            {complete.isPending ? "Saving…" : "Complete operation"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
