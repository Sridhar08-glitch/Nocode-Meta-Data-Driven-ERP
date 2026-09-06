"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { LotTrace } from "@/lib/manufacturing/api";
import {
  useCanManageManufacturing,
  useCreateNcr,
  useCreateQualityCheck,
  useLotTrace,
} from "@/lib/manufacturing/hooks";

/** Quality & traceability (Phase P2.12) — record a quality check or non-conformance against a
 * production order, and trace a finished lot back to its order, components and consumed lots. */
export function QualityPanel() {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <QualityCheckForm />
      <NcrForm />
      <div className="lg:col-span-2">
        <LotTraceLookup />
      </div>
    </div>
  );
}

export function QualityCheckForm() {
  const create = useCreateQualityCheck();
  const canManage = useCanManageManufacturing();
  const [orderId, setOrderId] = useState("");
  const [name, setName] = useState("");
  const [sampled, setSampled] = useState("0");
  const [passed, setPassed] = useState("0");
  const [failed, setFailed] = useState("0");

  async function save() {
    try {
      await create.mutateAsync({
        production_order_id: orderId.trim(),
        name: name.trim(),
        sampled_qty: sampled.trim() || "0",
        passed_qty: passed.trim() || "0",
        failed_qty: failed.trim() || "0",
      });
      toast.success("Quality check recorded");
      setName("");
      setSampled("0");
      setPassed("0");
      setFailed("0");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not record quality check");
    }
  }

  return (
    <div className="rounded-lg border p-4">
      <h2 className="text-lg font-medium">Quality check</h2>
      <p className="text-sm text-muted-foreground">Record a sample inspection against a production order.</p>
      <div className="mt-3 space-y-3">
        <div>
          <Label htmlFor="qc-order">Production order id</Label>
          <Input id="qc-order" value={orderId} onChange={(e) => setOrderId(e.target.value)} placeholder="MO UUID" />
        </div>
        <div>
          <Label htmlFor="qc-name">Check name</Label>
          <Input id="qc-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Dimensional inspection" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <Label htmlFor="qc-sampled">Sampled</Label>
            <Input id="qc-sampled" value={sampled} onChange={(e) => setSampled(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <Label htmlFor="qc-passed">Passed</Label>
            <Input id="qc-passed" value={passed} onChange={(e) => setPassed(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <Label htmlFor="qc-failed">Failed</Label>
            <Input id="qc-failed" value={failed} onChange={(e) => setFailed(e.target.value)} inputMode="decimal" />
          </div>
        </div>
        {canManage && (
          <Button onClick={save} disabled={create.isPending || !orderId.trim() || !name.trim()}>
            {create.isPending ? "Saving…" : "Record check"}
          </Button>
        )}
      </div>
    </div>
  );
}

export function NcrForm() {
  const create = useCreateNcr();
  const canManage = useCanManageManufacturing();
  const [orderId, setOrderId] = useState("");
  const [defect, setDefect] = useState("");

  async function save() {
    try {
      await create.mutateAsync({ production_order_id: orderId.trim(), defect: defect.trim() });
      toast.success("NCR raised");
      setDefect("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not raise NCR");
    }
  }

  return (
    <div className="rounded-lg border p-4">
      <h2 className="text-lg font-medium">Non-conformance (NCR)</h2>
      <p className="text-sm text-muted-foreground">Raise an NCR for a defect found on a production order.</p>
      <div className="mt-3 space-y-3">
        <div>
          <Label htmlFor="ncr-order">Production order id</Label>
          <Input id="ncr-order" value={orderId} onChange={(e) => setOrderId(e.target.value)} placeholder="MO UUID" />
        </div>
        <div>
          <Label htmlFor="ncr-defect">Defect</Label>
          <Input id="ncr-defect" value={defect} onChange={(e) => setDefect(e.target.value)} placeholder="Surface scratch" />
        </div>
        {canManage && (
          <Button onClick={save} disabled={create.isPending || !orderId.trim() || !defect.trim()}>
            {create.isPending ? "Saving…" : "Raise NCR"}
          </Button>
        )}
      </div>
    </div>
  );
}

export function LotTraceLookup() {
  const [lotInput, setLotInput] = useState("");
  const [lotId, setLotId] = useState<string | null>(null);
  const trace = useLotTrace(lotId ?? undefined);

  return (
    <div className="rounded-lg border p-4">
      <h2 className="text-lg font-medium">Lot traceability</h2>
      <p className="text-sm text-muted-foreground">
        Look up a finished lot to see its production order, components and consumed lots.
      </p>
      <form
        className="mt-3 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (lotInput.trim()) setLotId(lotInput.trim());
        }}
      >
        <div className="flex-1 min-w-[16rem]">
          <Label htmlFor="lot-id">Lot id</Label>
          <Input id="lot-id" value={lotInput} onChange={(e) => setLotInput(e.target.value)} placeholder="Lot UUID" />
        </div>
        <Button type="submit" disabled={!lotInput.trim()}>Trace</Button>
      </form>

      {lotId && (
        <div className="mt-4">
          {trace.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : trace.isError ? (
            <p className="rounded-md border p-3 text-sm text-destructive">Couldn&apos;t trace this lot.</p>
          ) : trace.data ? (
            <TraceResult data={trace.data} />
          ) : null}
        </div>
      )}
    </div>
  );
}

function TraceResult({ data }: { data: LotTrace }) {
  return (
    <div className="space-y-3 text-sm">
      <div className="rounded-md border p-3">
        <h3 className="mb-1 text-xs font-medium uppercase text-muted-foreground">Lot</h3>
        <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs">
          {JSON.stringify(data.lot, null, 2)}
        </pre>
      </div>
      {data.production_order && (
        <div className="rounded-md border p-3">
          <h3 className="mb-1 text-xs font-medium uppercase text-muted-foreground">Production order</h3>
          <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs">
            {JSON.stringify(data.production_order, null, 2)}
          </pre>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border p-3">
          <h3 className="mb-1 text-xs font-medium uppercase text-muted-foreground">
            Components ({data.components.length})
          </h3>
          {data.components.length === 0 ? (
            <p className="text-muted-foreground">None</p>
          ) : (
            <ul className="space-y-1 font-mono text-xs">
              {data.components.map((c, i) => (
                <li key={i} className="truncate">{JSON.stringify(c)}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-md border p-3">
          <h3 className="mb-1 text-xs font-medium uppercase text-muted-foreground">
            Consumed lots ({data.consumed_lots.length})
          </h3>
          {data.consumed_lots.length === 0 ? (
            <p className="text-muted-foreground">None</p>
          ) : (
            <ul className="space-y-1 font-mono text-xs">
              {data.consumed_lots.map((c, i) => (
                <li key={i} className="truncate">{JSON.stringify(c)}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
