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
import type {
  Kpi,
  KpiAggregate,
  KpiDirection,
  KpiInput,
  KpiSourceType,
} from "@/lib/analytics/api";
import {
  useCanManageAnalytics,
  useCreateKpi,
  useDeleteKpi,
  useKpis,
  useUpdateKpi,
} from "@/lib/analytics/hooks";

const AGGREGATES: KpiAggregate[] = ["sum", "avg", "count", "min", "max"];

function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/** The KPI registry table + create/edit/delete (admin). System KPIs are read-only. */
export function KpiRegistry() {
  const kpis = useKpis();
  const canManage = useCanManageAnalytics();
  const del = useDeleteKpi();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Kpi | null>(null);

  if (kpis.isError) return <ErrorState title="Couldn't load KPIs" />;

  const rows = kpis.data ?? [];

  async function remove(kpi: Kpi) {
    try {
      await del.mutateAsync(kpi.id);
      toast.success("KPI deleted");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete KPI");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">KPI registry</h2>
        {canManage && <Button size="sm" onClick={() => setCreating(true)}>New KPI</Button>}
      </div>
      {kpis.isLoading ? (
        <Skeleton className="h-48 w-full" />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No KPIs yet"
          description="Run setup on the scorecard to seed the standard registry, or create a KPI."
          action={canManage ? { label: "New KPI", onClick: () => setCreating(true) } : undefined}
        />
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2">Source</th>
                <th className="px-3 py-2 text-right">Target</th>
                <th className="px-3 py-2">Status</th>
                {canManage && <th className="px-3 py-2 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((k) => (
                <tr key={k.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">{k.code}</td>
                  <td className="px-3 py-2">
                    {k.name}
                    {k.is_system && (
                      <Badge variant="secondary" className="ml-2">system</Badge>
                    )}
                  </td>
                  <td className="px-3 py-2">{k.category}</td>
                  <td className="px-3 py-2">{k.source_type}</td>
                  <td className="px-3 py-2 text-right font-mono">{k.target ?? "—"}</td>
                  <td className="px-3 py-2">
                    <Badge variant={k.is_active ? "success" : "secondary"}>
                      {k.is_active ? "active" : "inactive"}
                    </Badge>
                  </td>
                  {canManage && (
                    <td className="px-3 py-2 text-right">
                      {k.is_system ? (
                        <span className="text-xs text-muted-foreground">read-only</span>
                      ) : (
                        <span className="flex justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={() => setEditing(k)}>
                            Edit
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => remove(k)}
                            disabled={del.isPending}
                          >
                            Delete
                          </Button>
                        </span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {creating && <KpiDialog onClose={() => setCreating(false)} />}
      {editing && <KpiDialog kpi={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

/** Create or edit a KPI. Source-type drives which source fields are shown. */
export function KpiDialog({ kpi, onClose }: { kpi?: Kpi; onClose: () => void }) {
  const create = useCreateKpi();
  const update = useUpdateKpi();
  const isEdit = !!kpi;

  const [code, setCode] = useState(kpi?.code ?? "");
  const [codeEdited, setCodeEdited] = useState(false);
  const [name, setName] = useState(kpi?.name ?? "");
  const [category, setCategory] = useState(kpi?.category ?? "");
  const [sourceType, setSourceType] = useState<KpiSourceType>(
    (kpi?.source_type as KpiSourceType) ?? "nql",
  );
  const [nqlSource, setNqlSource] = useState(kpi?.nql_source ?? "");
  const [valueField, setValueField] = useState(kpi?.value_field ?? "");
  const [aggregate, setAggregate] = useState<KpiAggregate>(
    (kpi?.aggregate as KpiAggregate) ?? "sum",
  );
  const [nativeKey, setNativeKey] = useState(kpi?.native_key ?? "");
  const [target, setTarget] = useState(kpi?.target ?? "");
  const [warning, setWarning] = useState(kpi?.warning_threshold ?? "");
  const [direction, setDirection] = useState<KpiDirection>(
    (kpi?.direction as KpiDirection) ?? "higher_better",
  );
  const [unit, setUnit] = useState(kpi?.unit ?? "");

  const pending = create.isPending || update.isPending;

  function onNameChange(v: string) {
    setName(v);
    if (!isEdit && !codeEdited) setCode(slugify(v));
  }

  async function save() {
    const payload: KpiInput = {
      code: code.trim(),
      name: name.trim(),
      category: category.trim(),
      source_type: sourceType,
      target: target.trim() || null,
      warning_threshold: warning.trim() || null,
      direction,
      unit: unit.trim(),
    };
    if (sourceType === "nql") {
      payload.nql_source = nqlSource.trim();
      payload.value_field = valueField.trim();
      payload.aggregate = aggregate;
    } else {
      payload.native_key = nativeKey.trim();
    }

    try {
      if (isEdit && kpi) await update.mutateAsync({ id: kpi.id, data: payload });
      else await create.mutateAsync(payload);
      toast.success(isEdit ? "KPI updated" : "KPI created");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save KPI");
    }
  }

  const canSave =
    !!name.trim() &&
    !!code.trim() &&
    !!category.trim() &&
    (sourceType === "nql" ? !!nqlSource.trim() : !!nativeKey.trim());

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit KPI" : "New KPI"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="kpi-name">Name</Label>
              <Input id="kpi-name" value={name} onChange={(e) => onNameChange(e.target.value)} />
            </div>
            <div className="flex-1">
              <Label htmlFor="kpi-code">Code</Label>
              <Input
                id="kpi-code"
                value={code}
                onChange={(e) => {
                  setCodeEdited(true);
                  setCode(e.target.value);
                }}
                disabled={isEdit}
                placeholder="kpi_slug"
              />
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="kpi-category">Category</Label>
              <Input
                id="kpi-category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="finance"
              />
            </div>
            <div className="w-40">
              <Label htmlFor="kpi-source">Source type</Label>
              <Select value={sourceType} onValueChange={(v) => setSourceType(v as KpiSourceType)}>
                <SelectTrigger id="kpi-source" aria-label="Source type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="nql">NQL query</SelectItem>
                  <SelectItem value="native">Native key</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {sourceType === "nql" ? (
            <>
              <div>
                <Label htmlFor="kpi-nql">NQL source</Label>
                <Input
                  id="kpi-nql"
                  value={nqlSource}
                  onChange={(e) => setNqlSource(e.target.value)}
                  placeholder="invoice where status = &quot;paid&quot;"
                />
              </div>
              <div className="flex gap-3">
                <div className="flex-1">
                  <Label htmlFor="kpi-field">Value field</Label>
                  <Input
                    id="kpi-field"
                    value={valueField}
                    onChange={(e) => setValueField(e.target.value)}
                    placeholder="amount"
                  />
                </div>
                <div className="w-40">
                  <Label htmlFor="kpi-agg">Aggregate</Label>
                  <Select value={aggregate} onValueChange={(v) => setAggregate(v as KpiAggregate)}>
                    <SelectTrigger id="kpi-agg" aria-label="Aggregate">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {AGGREGATES.map((a) => (
                        <SelectItem key={a} value={a}>
                          {a}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </>
          ) : (
            <div>
              <Label htmlFor="kpi-native">Native key</Label>
              <Input
                id="kpi-native"
                value={nativeKey}
                onChange={(e) => setNativeKey(e.target.value)}
                placeholder="server-resolved metric key"
              />
            </div>
          )}

          <div className="flex gap-3">
            <div className="w-28">
              <Label htmlFor="kpi-target">Target</Label>
              <Input id="kpi-target" value={target ?? ""} onChange={(e) => setTarget(e.target.value)} inputMode="decimal" />
            </div>
            <div className="w-28">
              <Label htmlFor="kpi-warn">Warning</Label>
              <Input id="kpi-warn" value={warning ?? ""} onChange={(e) => setWarning(e.target.value)} inputMode="decimal" />
            </div>
            <div className="w-24">
              <Label htmlFor="kpi-unit">Unit</Label>
              <Input id="kpi-unit" value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="%" />
            </div>
            <div className="flex-1">
              <Label htmlFor="kpi-dir">Direction</Label>
              <Select value={direction} onValueChange={(v) => setDirection(v as KpiDirection)}>
                <SelectTrigger id="kpi-dir" aria-label="Direction">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="higher_better">Higher is better</SelectItem>
                  <SelectItem value="lower_better">Lower is better</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={pending || !canSave}>
            {pending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
