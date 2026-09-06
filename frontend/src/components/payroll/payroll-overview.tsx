"use client";

import { useState } from "react";

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
import { ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { PayFrequency } from "@/lib/payroll/api";
import {
  useCanManagePayroll,
  useRunSetup,
  useSettings,
  useUpdateSettings,
} from "@/lib/payroll/hooks";

const FREQUENCIES: { value: PayFrequency; label: string }[] = [
  { value: "monthly", label: "Monthly" },
  { value: "semimonthly", label: "Semi-monthly" },
  { value: "biweekly", label: "Bi-weekly" },
  { value: "weekly", label: "Weekly" },
];

/** Payroll overview (Phase P2.8) — settings summary, the admin-only "Run setup" action that
 * ensures payslip numbering, and a settings editor. The run/posting math is server-side. */
export function PayrollOverview() {
  const settings = useSettings();
  const setup = useRunSetup();
  const canManage = useCanManagePayroll();
  const [editing, setEditing] = useState(false);

  async function doSetup() {
    try {
      const res = await setup.mutateAsync();
      toast.success(res.detail || "Payroll setup complete");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not run setup");
    }
  }

  if (settings.isLoading) return <Skeleton className="h-48 w-full" />;
  if (settings.isError) return <ErrorState title="Couldn't load payroll settings" />;

  const s = settings.data;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border p-4">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-medium">Settings</h2>
          {canManage && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                Edit settings
              </Button>
              <Button size="sm" onClick={doSetup} disabled={setup.isPending}>
                {setup.isPending ? "Running…" : "Run setup"}
              </Button>
            </div>
          )}
        </div>
        {s && (
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
            <Field label="Frequency" value={s.frequency} />
            <Field label="Currency" value={s.currency} />
            <Field label="Default country" value={s.default_country} />
            <Field label="Cost center" value={s.default_cost_center || "—"} />
            <Field label="Pay start day" value={String(s.pay_start_day)} />
            <Field label="Pay end day" value={String(s.pay_end_day)} />
          </dl>
        )}
      </div>

      {editing && s && <SettingsDialog onClose={() => setEditing(false)} initial={s} />}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function SettingsDialog({
  onClose,
  initial,
}: {
  onClose: () => void;
  initial: { frequency: string; currency: string; default_country: string; default_cost_center: string; pay_start_day: number; pay_end_day: number };
}) {
  const update = useUpdateSettings();
  const [frequency, setFrequency] = useState(initial.frequency);
  const [currency, setCurrency] = useState(initial.currency);
  const [country, setCountry] = useState(initial.default_country);
  const [costCenter, setCostCenter] = useState(initial.default_cost_center);
  const [startDay, setStartDay] = useState(String(initial.pay_start_day));
  const [endDay, setEndDay] = useState(String(initial.pay_end_day));

  async function save() {
    try {
      await update.mutateAsync({
        frequency,
        currency: currency.trim(),
        default_country: country.trim(),
        default_cost_center: costCenter.trim(),
        pay_start_day: Number(startDay) || 1,
        pay_end_day: Number(endDay) || 28,
      });
      toast.success("Settings saved");
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save settings");
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Payroll settings</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="pr-freq">Frequency</Label>
            <Select value={frequency} onValueChange={setFrequency}>
              <SelectTrigger id="pr-freq" aria-label="Frequency"><SelectValue /></SelectTrigger>
              <SelectContent>
                {FREQUENCIES.map((f) => (
                  <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex gap-3">
            <div className="w-28">
              <Label htmlFor="pr-cur">Currency</Label>
              <Input id="pr-cur" value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="USD" />
            </div>
            <div className="w-28">
              <Label htmlFor="pr-country">Country</Label>
              <Input id="pr-country" value={country} onChange={(e) => setCountry(e.target.value)} placeholder="US" />
            </div>
            <div className="flex-1">
              <Label htmlFor="pr-cc">Cost center</Label>
              <Input id="pr-cc" value={costCenter} onChange={(e) => setCostCenter(e.target.value)} />
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="pr-start">Pay start day</Label>
              <Input id="pr-start" value={startDay} onChange={(e) => setStartDay(e.target.value)} inputMode="numeric" />
            </div>
            <div className="flex-1">
              <Label htmlFor="pr-end">Pay end day</Label>
              <Input id="pr-end" value={endDay} onChange={(e) => setEndDay(e.target.value)} inputMode="numeric" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={update.isPending}>
            {update.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
