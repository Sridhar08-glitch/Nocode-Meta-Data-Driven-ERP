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
import type { CalcType, ComponentType } from "@/lib/payroll/api";
import {
  useCanManagePayroll,
  useComponents,
  useCreateComponent,
  useStructure,
} from "@/lib/payroll/hooks";

const TYPES: { value: ComponentType; label: string }[] = [
  { value: "earning", label: "Earning" },
  { value: "deduction", label: "Deduction" },
  { value: "benefit", label: "Benefit" },
];
const CALC_TYPES: { value: CalcType; label: string }[] = [
  { value: "fixed", label: "Fixed amount" },
  { value: "formula", label: "Formula" },
  { value: "percent", label: "Percent of base" },
];

/** Salary structure detail (Phase P2.8) — its component list + add component. Component calc
 * (fixed / formula / percent) is evaluated server-side at run time. */
export function StructureDetail({ structureId }: { structureId: string }) {
  const structure = useStructure(structureId);
  const components = useComponents(structureId);
  const canManage = useCanManagePayroll();
  const [adding, setAdding] = useState(false);

  if (structure.isLoading || components.isLoading) return <Skeleton className="h-64 w-full" />;
  if (structure.isError) return <ErrorState title="Couldn't load structure" />;

  const st = structure.data;
  const rows = (components.data ?? []).slice().sort((a, b) => a.sequence - b.sequence);

  return (
    <div className="space-y-4">
      {st && (
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">{st.name}</h1>
          <Badge variant={st.status === "active" ? "success" : "secondary"}>{st.status}</Badge>
          <span className="text-sm text-muted-foreground">
            {st.currency} · {st.country} · {st.effective_date}
          </span>
        </div>
      )}

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Components</h2>
        {canManage && <Button size="sm" onClick={() => setAdding(true)}>Add component</Button>}
      </div>

      {rows.length === 0 ? (
        <EmptyState title="No components" description="Add earnings and deductions to this structure." />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Seq</th>
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Calc</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2">Taxable</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id} className="border-b last:border-0">
                  <td className="px-3 py-2 text-muted-foreground">{c.sequence}</td>
                  <td className="px-3 py-2 font-mono">{c.code}</td>
                  <td className="px-3 py-2">{c.name}</td>
                  <td className="px-3 py-2">
                    <Badge variant={c.component_type === "deduction" ? "destructive" : "secondary"}>
                      {c.component_type}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{c.calc_type}</td>
                  <td className="px-3 py-2 text-right font-mono">
                    {c.calc_type === "formula" ? c.formula || "—" : c.amount}
                  </td>
                  <td className="px-3 py-2">{c.taxable ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {adding && <ComponentDialog structureId={structureId} nextSeq={rows.length + 1} onClose={() => setAdding(false)} />}
    </div>
  );
}

function ComponentDialog({
  structureId,
  nextSeq,
  onClose,
}: {
  structureId: string;
  nextSeq: number;
  onClose: () => void;
}) {
  const create = useCreateComponent(structureId);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState<ComponentType>("earning");
  const [calcType, setCalcType] = useState<CalcType>("fixed");
  const [amount, setAmount] = useState("0");
  const [formula, setFormula] = useState("");
  const [sequence, setSequence] = useState(String(nextSeq));
  const [taxable, setTaxable] = useState(true);

  async function save() {
    try {
      await create.mutateAsync({
        salary_structure_id: structureId,
        code: code.trim(),
        name: name.trim(),
        component_type: type,
        calc_type: calcType,
        amount: calcType === "formula" ? "0" : amount.trim() || "0",
        formula: calcType === "formula" ? formula.trim() : "",
        sequence: Number(sequence) || nextSeq,
        taxable,
      });
      toast.success("Component added");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add component");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add component</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="w-32">
              <Label htmlFor="cmp-code">Code</Label>
              <Input id="cmp-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="BASIC" />
            </div>
            <div className="flex-1">
              <Label htmlFor="cmp-name">Name</Label>
              <Input id="cmp-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Basic salary" />
            </div>
            <div className="w-20">
              <Label htmlFor="cmp-seq">Seq</Label>
              <Input id="cmp-seq" value={sequence} onChange={(e) => setSequence(e.target.value)} inputMode="numeric" />
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="cmp-type">Type</Label>
              <Select value={type} onValueChange={(v) => setType(v as ComponentType)}>
                <SelectTrigger id="cmp-type" aria-label="Component type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1">
              <Label htmlFor="cmp-calc">Calc type</Label>
              <Select value={calcType} onValueChange={(v) => setCalcType(v as CalcType)}>
                <SelectTrigger id="cmp-calc" aria-label="Calc type"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CALC_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          {calcType === "formula" ? (
            <div>
              <Label htmlFor="cmp-formula">Formula</Label>
              <Input id="cmp-formula" value={formula} onChange={(e) => setFormula(e.target.value)} placeholder="base * 0.1" />
            </div>
          ) : (
            <div className="w-40">
              <Label htmlFor="cmp-amount">Amount</Label>
              <Input id="cmp-amount" value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" />
            </div>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={taxable} onChange={(e) => setTaxable(e.target.checked)} />
            Taxable
          </label>
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
