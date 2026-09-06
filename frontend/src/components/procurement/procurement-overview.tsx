"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useEnsureSetup, usePostGoodsReceipt, usePostVendorBill } from "@/lib/procurement/hooks";
import { useInstalledSolutions } from "@/lib/solution-templates/hooks";
import { useTenant } from "@/lib/tenant/context";

const PROCUREMENT_SLUG = "procurement";

/** Procurement lifecycle stages → the generic F1.7 record-list route for each entity. */
const STAGES: { href: string; label: string; description: string }[] = [
  { href: "/e/vendor", label: "Vendors", description: "Suppliers and their contacts." },
  { href: "/e/rfq", label: "RFQs", description: "Requests for quotation sent to vendors." },
  { href: "/e/purchase_order", label: "Purchase orders", description: "Approved orders placed with vendors." },
  { href: "/e/goods_receipt", label: "Goods receipts", description: "Received goods — post to add stock." },
  { href: "/e/vendor_bill", label: "Vendor bills", description: "Supplier invoices — post to the ledger." },
];

/** Whether the caller may run setup (the API gates the action regardless). */
function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/**
 * Procurement Solution overview (Phase P2.5). Ties the procurement lifecycle together: links to the
 * generic entity screens + the native lifecycle actions (setup, post goods receipt, post vendor bill)
 * the metadata runtime can't express. If the Procurement solution isn't installed, prompts to install it.
 */
export function ProcurementOverview() {
  const canManage = useCanManage();
  const installed = useInstalledSolutions();

  if (installed.isLoading) return <Skeleton className="h-64 w-full" />;
  if (installed.isError) return <ErrorState title="Couldn't load installed solutions" />;

  const isInstalled = (installed.data?.results ?? []).some((s) => s.solution_slug === PROCUREMENT_SLUG);

  if (!isInstalled) return <NotInstalled />;

  return (
    <div className="space-y-6">
      <LifecycleStages />
      {canManage && <RunSetup />}
      <LifecycleActions />
    </div>
  );
}

export function NotInstalled() {
  return (
    <div className="space-y-4">
      <EmptyState
        title="Procurement isn't installed yet"
        description="Install the Procurement solution to provision vendors, RFQs, purchase orders, goods receipts, and vendor bills."
      />
      <div className="flex flex-wrap justify-center gap-2">
        <Button asChild>
          <Link href="/solutions">Browse solutions</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/solutions/new">Create solution</Link>
        </Button>
      </div>
    </div>
  );
}

function LifecycleStages() {
  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {STAGES.map((s) => (
        <li key={s.href}>
          <Link
            href={s.href}
            className="flex h-full flex-col gap-1 rounded-lg border p-4 transition-colors hover:bg-accent"
          >
            <span className="font-medium">{s.label}</span>
            <span className="text-xs text-muted-foreground">{s.description}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function RunSetup() {
  const setup = useEnsureSetup();
  async function run() {
    try {
      const res = await setup.mutateAsync();
      toast.success(res.detail || "Procurement number sequences ready");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Setup failed");
    }
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
      <div>
        <p className="text-sm font-medium">Document numbering</p>
        <p className="text-xs text-muted-foreground">
          Ensure gapless RFQ / PO / goods-receipt / vendor-bill number sequences exist.
        </p>
      </div>
      <Button onClick={run} disabled={setup.isPending}>
        {setup.isPending ? "Running…" : "Run setup"}
      </Button>
    </div>
  );
}

export function LifecycleActions() {
  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div>
        <h2 className="text-sm font-medium">Lifecycle actions</h2>
        <p className="text-xs text-muted-foreground">
          Post a document by its record id. (Deep per-record action buttons inside the generic record
          runtime are out of scope, so the id is entered here.)
        </p>
      </div>
      <PostAction
        label="Post goods receipt"
        placeholder="Goods receipt record id"
        useAction={usePostGoodsReceipt}
        successText="Goods receipt posted — stock updated"
      />
      <PostAction
        label="Post vendor bill"
        placeholder="Vendor bill record id"
        useAction={usePostVendorBill}
        successText="Vendor bill posted to the ledger"
      />
    </div>
  );
}

function PostAction({
  label,
  placeholder,
  useAction,
  successText,
}: {
  label: string;
  placeholder: string;
  useAction: () => { mutateAsync: (id: string) => Promise<unknown>; isPending: boolean };
  successText: string;
}) {
  const action = useAction();
  const [id, setId] = useState("");

  async function run() {
    const recordId = id.trim();
    if (!recordId) return;
    try {
      await action.mutateAsync(recordId);
      toast.success(successText);
      setId("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : `${label} failed`);
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex-1 space-y-1">
        <span className="text-xs font-medium">{label}</span>
        <Input
          aria-label={label}
          placeholder={placeholder}
          value={id}
          onChange={(e) => setId(e.target.value)}
        />
      </label>
      <Button onClick={run} disabled={!id.trim() || action.isPending}>
        {action.isPending ? "Posting…" : "Post"}
      </Button>
    </div>
  );
}

export { PROCUREMENT_SLUG, STAGES };
