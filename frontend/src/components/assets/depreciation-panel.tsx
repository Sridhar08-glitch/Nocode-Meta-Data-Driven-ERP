"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import type { DepreciationMethod, DepreciationPreviewRow, DepreciationSchedule } from "@/lib/assets/api";
import {
  useCreateSchedule,
  useDepreciationPreview,
  useRunAllDepreciation,
  useRunDepreciation,
  useScheduleEntries,
  useSchedules,
} from "@/lib/assets/hooks";
import { useTenant } from "@/lib/tenant/context";

const METHODS: { value: DepreciationMethod; label: string }[] = [
  { value: "straight_line", label: "Straight line" },
  { value: "declining_balance", label: "Declining balance" },
  { value: "double_declining", label: "Double declining" },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function useCanManage(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

/** Native depreciation engine (Phase P2.9) — create schedules, post immutable period runs,
 * inspect entries, and preview a full schedule without writing. Depreciation math is server-side. */
export function DepreciationPanel() {
  const canManage = useCanManage();
  return (
    <div className="space-y-6">
      <CreateScheduleForm />
      <SchedulesList canManage={canManage} />
      <PreviewForm />
    </div>
  );
}

export function CreateScheduleForm() {
  const create = useCreateSchedule();
  const [assetRecordId, setAssetRecordId] = useState("");
  const [method, setMethod] = useState<DepreciationMethod>("straight_line");
  const [cost, setCost] = useState("");
  const [salvage, setSalvage] = useState("");
  const [life, setLife] = useState("");
  const [startDate, setStartDate] = useState(todayIso());

  async function save() {
    const asset = assetRecordId.trim();
    const months = Number(life);
    if (!asset || !cost.trim() || !Number.isInteger(months) || months <= 0) {
      toast.error("Asset id, acquisition cost and a positive useful life (months) are required");
      return;
    }
    try {
      await create.mutateAsync({
        asset_record_id: asset,
        method,
        acquisition_cost: cost.trim(),
        salvage_value: salvage.trim() || "0",
        useful_life_months: months,
        start_date: startDate,
      });
      toast.success("Schedule created");
      setAssetRecordId("");
      setCost("");
      setSalvage("");
      setLife("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create schedule");
    }
  }

  return (
    <div className="max-w-2xl space-y-3 rounded-lg border p-4">
      <h2 className="text-sm font-medium">New depreciation schedule</h2>
      <p className="text-xs text-muted-foreground">Enter the asset record id (raw UUID — no picker yet).</p>
      <div>
        <Label htmlFor="dep-asset">Asset record id</Label>
        <Input id="dep-asset" value={assetRecordId} onChange={(e) => setAssetRecordId(e.target.value)} placeholder="asset record id" />
      </div>
      <div className="flex flex-wrap gap-3">
        <div className="w-56">
          <Label htmlFor="dep-method">Method</Label>
          <Select value={method} onValueChange={(v) => setMethod(v as DepreciationMethod)}>
            <SelectTrigger id="dep-method" aria-label="Method">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METHODS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-40">
          <Label htmlFor="dep-cost">Acquisition cost</Label>
          <Input id="dep-cost" inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} placeholder="10000" />
        </div>
        <div className="w-40">
          <Label htmlFor="dep-salvage">Salvage value</Label>
          <Input id="dep-salvage" inputMode="decimal" value={salvage} onChange={(e) => setSalvage(e.target.value)} placeholder="500" />
        </div>
        <div className="w-40">
          <Label htmlFor="dep-life">Useful life (months)</Label>
          <Input id="dep-life" inputMode="numeric" value={life} onChange={(e) => setLife(e.target.value)} placeholder="60" />
        </div>
        <div className="w-44">
          <Label htmlFor="dep-start">Start date</Label>
          <Input id="dep-start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
        </div>
      </div>
      <div className="flex justify-end">
        <Button onClick={save} disabled={create.isPending}>
          {create.isPending ? "Saving…" : "Create schedule"}
        </Button>
      </div>
    </div>
  );
}

export function SchedulesList({ canManage }: { canManage: boolean }) {
  const [filter, setFilter] = useState("");
  const schedules = useSchedules(filter.trim() || undefined);
  const [selected, setSelected] = useState<string | null>(null);
  const runAll = useRunAllDepreciation();

  const rows = schedules.data ?? [];

  async function doRunAll() {
    try {
      const res = await runAll.mutateAsync(todayIso());
      toast.success(`Posted ${res.posted} entr${res.posted === 1 ? "y" : "ies"}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Run all failed");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <label className="w-72 space-y-1">
          <span className="text-xs font-medium">Filter by asset record id</span>
          <Input aria-label="Filter schedules by asset record id" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="asset record id" />
        </label>
        {canManage && (
          <Button variant="outline" onClick={doRunAll} disabled={runAll.isPending}>
            {runAll.isPending ? "Running…" : "Run all (today)"}
          </Button>
        )}
      </div>

      {schedules.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : schedules.isError ? (
        <ErrorState title="Couldn't load schedules" />
      ) : rows.length === 0 ? (
        <EmptyState title="No depreciation schedules" description="Create a schedule above to start posting depreciation." />
      ) : (
        <ul className="space-y-1">
          {rows.map((s) => (
            <ScheduleRow key={s.id} schedule={s} selected={selected === s.id} onSelect={() => setSelected(selected === s.id ? null : s.id)} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ScheduleRow({
  schedule,
  selected,
  onSelect,
}: {
  schedule: DepreciationSchedule;
  selected: boolean;
  onSelect: () => void;
}) {
  const run = useRunDepreciation();
  const entries = useScheduleEntries(selected ? schedule.id : null);

  async function doRun() {
    try {
      const res = await run.mutateAsync({ scheduleId: schedule.id, periodDate: todayIso() });
      if (res.detail) toast.info(res.detail);
      else toast.success(`Period ${res.period_index} posted — NBV ${res.net_book_value}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Run failed");
    }
  }

  return (
    <li className="rounded-md border">
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
        <button className="flex items-center gap-2 text-left" onClick={onSelect} aria-expanded={selected} aria-label={`Schedule ${schedule.id}`}>
          <span className="font-mono text-xs text-muted-foreground">{schedule.asset_record_id.slice(0, 8)}</span>
          <span>{METHODS.find((m) => m.value === schedule.method)?.label ?? schedule.method}</span>
          <Badge variant={schedule.status === "active" ? "default" : "secondary"}>{schedule.status}</Badge>
        </button>
        <div className="flex items-center gap-3">
          <span className="font-mono text-xs text-muted-foreground">
            {schedule.acquisition_cost} → {schedule.salvage_value} / {schedule.useful_life_months}mo
          </span>
          <Button size="sm" onClick={doRun} disabled={run.isPending}>
            {run.isPending ? "Running…" : "Run period"}
          </Button>
        </div>
      </div>
      {selected && (
        <div className="border-t px-3 py-2">
          {entries.isLoading ? (
            <Skeleton className="h-20 w-full" />
          ) : (entries.data ?? []).length === 0 ? (
            <p className="py-2 text-xs text-muted-foreground">No entries posted yet.</p>
          ) : (
            <EntriesTable rows={entries.data ?? []} />
          )}
        </div>
      )}
    </li>
  );
}

function EntriesTable({ rows }: { rows: { period_index: number; amount: string; accumulated: string; net_book_value: string }[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="border-b text-left text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-2 py-1.5">Period</th>
            <th className="px-2 py-1.5 text-right">Amount</th>
            <th className="px-2 py-1.5 text-right">Accumulated</th>
            <th className="px-2 py-1.5 text-right">Net book value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.period_index} className="border-b last:border-0">
              <td className="px-2 py-1.5">{r.period_index}</td>
              <td className="px-2 py-1.5 text-right font-mono">{r.amount}</td>
              <td className="px-2 py-1.5 text-right font-mono">{r.accumulated}</td>
              <td className="px-2 py-1.5 text-right font-mono">{r.net_book_value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PreviewForm() {
  const preview = useDepreciationPreview();
  const [method, setMethod] = useState<DepreciationMethod>("straight_line");
  const [cost, setCost] = useState("");
  const [salvage, setSalvage] = useState("");
  const [life, setLife] = useState("");
  const [rows, setRows] = useState<DepreciationPreviewRow[]>([]);

  async function run() {
    const months = Number(life);
    if (!cost.trim() || !Number.isInteger(months) || months <= 0) {
      toast.error("Acquisition cost and a positive useful life (months) are required");
      return;
    }
    try {
      const res = await preview.mutateAsync({
        method,
        acquisition_cost: cost.trim(),
        salvage_value: salvage.trim() || "0",
        useful_life_months: months,
      });
      setRows(res);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Preview failed");
    }
  }

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div>
        <h2 className="text-sm font-medium">Preview a schedule</h2>
        <p className="text-xs text-muted-foreground">Compute the full schedule without writing any entry to the database.</p>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-56">
          <Label htmlFor="prev-method">Method</Label>
          <Select value={method} onValueChange={(v) => setMethod(v as DepreciationMethod)}>
            <SelectTrigger id="prev-method" aria-label="Preview method">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METHODS.map((m) => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="w-40">
          <Label htmlFor="prev-cost">Acquisition cost</Label>
          <Input id="prev-cost" inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} placeholder="10000" />
        </div>
        <div className="w-40">
          <Label htmlFor="prev-salvage">Salvage value</Label>
          <Input id="prev-salvage" inputMode="decimal" value={salvage} onChange={(e) => setSalvage(e.target.value)} placeholder="500" />
        </div>
        <div className="w-40">
          <Label htmlFor="prev-life">Useful life (months)</Label>
          <Input id="prev-life" inputMode="numeric" value={life} onChange={(e) => setLife(e.target.value)} placeholder="60" />
        </div>
        <Button onClick={run} disabled={preview.isPending}>
          {preview.isPending ? "Computing…" : "Preview"}
        </Button>
      </div>
      {rows.length > 0 && <EntriesTable rows={rows} />}
    </div>
  );
}
