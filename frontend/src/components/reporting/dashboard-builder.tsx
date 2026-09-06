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
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import {
  type Dashboard,
  type DashboardWidgetType,
  type Report,
  WIDGET_TYPE_OPTIONS,
} from "@/lib/reporting/api";
import { useCreateWidget, useDeleteWidget } from "@/lib/reporting/hooks";

const BINDS_REPORT = new Set<DashboardWidgetType>(["report", "metric_card"]);

/** Dashboard builder (Phase F2.3): add/remove widgets. Grid width via numeric span (no dnd dep). */
export function DashboardBuilder({ dashboard, reports }: { dashboard: Dashboard; reports: Report[] }) {
  const del = useDeleteWidget(dashboard.id);
  const [adding, setAdding] = useState(false);

  async function remove(wid: string) {
    try {
      await del.mutateAsync(wid);
      toast.success("Widget removed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not remove widget");
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">{dashboard.widgets.length} widgets</h3>
        <Button size="sm" onClick={() => setAdding(true)}>
          Add widget
        </Button>
      </div>
      <ul className="space-y-2">
        {dashboard.widgets.map((w) => (
          <li key={w.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
            <span className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{w.title || "(untitled)"}</span>
              <Badge variant="outline">{w.widget_type}</Badge>
              <span className="text-xs text-muted-foreground">span {w.grid_w}</span>
            </span>
            <Button
              variant="ghost"
              size="sm"
              aria-label={`Remove widget ${w.title || w.widget_type}`}
              onClick={() => remove(w.id)}
              disabled={del.isPending}
            >
              Delete
            </Button>
          </li>
        ))}
        {dashboard.widgets.length === 0 && (
          <li className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">No widgets yet.</li>
        )}
      </ul>
      {adding && <AddWidgetDialog dashboardId={dashboard.id} reports={reports} open onOpenChange={setAdding} />}
    </div>
  );
}

function AddWidgetDialog({
  dashboardId,
  reports,
  open,
  onOpenChange,
}: {
  dashboardId: string;
  reports: Report[];
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const create = useCreateWidget(dashboardId);
  const [type, setType] = useState<DashboardWidgetType>("report");
  const [title, setTitle] = useState("");
  const [reportId, setReportId] = useState("");
  const [width, setWidth] = useState(6);
  const needsReport = BINDS_REPORT.has(type);
  const valid = !needsReport || !!reportId;

  async function submit() {
    if (!valid) return;
    try {
      await create.mutateAsync({
        widget_type: type,
        title: title.trim(),
        report_id: needsReport ? reportId : null,
        grid_w: width,
      });
      toast.success("Widget added");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add widget");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add widget</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="w-type">Type</Label>
            <Select value={type} onValueChange={(v) => setType(v as DashboardWidgetType)}>
              <SelectTrigger id="w-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {WIDGET_TYPE_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="w-title">Title</Label>
            <Input id="w-title" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
          </div>
          {needsReport && (
            <div className="space-y-1.5">
              <Label htmlFor="w-report">Report</Label>
              <Select value={reportId || undefined} onValueChange={setReportId}>
                <SelectTrigger id="w-report">
                  <SelectValue placeholder="Pick a report" />
                </SelectTrigger>
                <SelectContent>
                  {reports.map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="w-width">Width (1–12 columns)</Label>
            <Input
              id="w-width"
              type="number"
              min={1}
              max={12}
              value={width}
              onChange={(e) => setWidth(Math.min(Math.max(Number(e.target.value) || 1, 1), 12))}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!valid || create.isPending}>
            {create.isPending ? "Adding…" : "Add widget"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
