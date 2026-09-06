"use client";

import Link from "next/link";
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
import { useCanManagePayroll, useCreateStructure, useStructures } from "@/lib/payroll/hooks";

/** Salary structures (Phase P2.8) — list + create. Each structure groups the earning/deduction
 * components used to compute payslips. Drill in to manage components. */
export function StructuresPanel() {
  const structures = useStructures();
  const canManage = useCanManagePayroll();
  const [creating, setCreating] = useState(false);

  const rows = structures.data ?? [];

  if (structures.isLoading) return <Skeleton className="h-64 w-full" />;
  if (structures.isError) return <ErrorState title="Couldn't load salary structures" />;

  return (
    <div className="space-y-3">
      {canManage && (
        <div className="flex justify-end">
          <Button onClick={() => setCreating(true)}>New structure</Button>
        </div>
      )}
      {rows.length === 0 ? (
        <EmptyState
          title="No salary structures"
          description="Create a structure to define the earnings and deductions used in payroll runs."
          action={canManage ? { label: "New structure", onClick: () => setCreating(true) } : undefined}
        />
      ) : (
        <ul className="space-y-1">
          {rows.map((st) => (
            <li key={st.id}>
              <Link
                href={`/payroll/structures/${st.id}`}
                className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm transition-colors hover:bg-accent"
              >
                <span className="flex items-center gap-2">
                  <span className="font-medium">{st.name}</span>
                  <Badge variant={st.status === "active" ? "success" : "secondary"}>{st.status}</Badge>
                </span>
                <span className="flex items-center gap-3 text-muted-foreground">
                  <span>{st.currency}</span>
                  <span>{st.country}</span>
                  <span>{st.effective_date}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {creating && <StructureDialog onClose={() => setCreating(false)} />}
    </div>
  );
}

function StructureDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateStructure();
  const [name, setName] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [country, setCountry] = useState("US");
  const [effectiveDate, setEffectiveDate] = useState("");

  async function save() {
    try {
      await create.mutateAsync({
        name: name.trim(),
        currency: currency.trim() || "USD",
        country: country.trim() || "US",
        effective_date: effectiveDate || undefined,
      });
      toast.success("Structure created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create structure");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New salary structure</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="st-name">Name</Label>
            <Input id="st-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Standard monthly" />
          </div>
          <div className="flex gap-3">
            <div className="w-28">
              <Label htmlFor="st-cur">Currency</Label>
              <Input id="st-cur" value={currency} onChange={(e) => setCurrency(e.target.value)} />
            </div>
            <div className="w-28">
              <Label htmlFor="st-country">Country</Label>
              <Input id="st-country" value={country} onChange={(e) => setCountry(e.target.value)} />
            </div>
            <div className="flex-1">
              <Label htmlFor="st-date">Effective date</Label>
              <Input id="st-date" type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={create.isPending || !name.trim()}>
            {create.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
