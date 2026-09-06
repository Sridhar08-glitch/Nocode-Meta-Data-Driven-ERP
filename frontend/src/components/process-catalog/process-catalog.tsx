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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import type { BlueprintSummary, ProcessBlueprint } from "@/lib/process-catalog/api";
import { useBlueprintPreview, useBlueprints, useInstallBlueprint } from "@/lib/process-catalog/hooks";

const SUMMARY_LABELS: { key: keyof BlueprintSummary; label: string }[] = [
  { key: "entities", label: "Entities" },
  { key: "workflows", label: "Workflows" },
  { key: "rules", label: "Rules" },
  { key: "reports", label: "Reports" },
  { key: "notification_templates", label: "Templates" },
];

/** Business Process Catalog (Phase F2.9): browse published blueprints, preview, and install. */
export function ProcessCatalog() {
  const [search, setSearch] = useState("");
  const blueprints = useBlueprints(search.trim() ? { search: search.trim() } : {});
  const [previewing, setPreviewing] = useState<ProcessBlueprint | null>(null);

  const rows = blueprints.data?.results ?? [];

  return (
    <div className="space-y-4">
      <Input
        aria-label="Search processes"
        placeholder="Search processes…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="max-w-sm"
      />

      {blueprints.isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : blueprints.isError ? (
        <ErrorState title="Couldn't load the catalog" />
      ) : rows.length === 0 ? (
        <EmptyState title="No processes found" description="No published process blueprints match your search." />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                onClick={() => setPreviewing(b)}
                aria-label={`Preview ${b.name}`}
                className="flex h-full w-full flex-col items-start gap-1 rounded-lg border p-4 text-left transition-colors hover:bg-accent"
              >
                <div className="flex w-full items-center justify-between gap-2">
                  <span className="font-medium">{b.name}</span>
                  {b.category && <Badge variant="outline">{b.category}</Badge>}
                </div>
                {b.description && <span className="line-clamp-2 text-xs text-muted-foreground">{b.description}</span>}
                <span className="mt-auto text-xs text-muted-foreground">{b.install_count} install(s)</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {previewing && <PreviewDialog open blueprint={previewing} onClose={() => setPreviewing(null)} />}
    </div>
  );
}

function PreviewDialog({ open, blueprint, onClose }: { open: boolean; blueprint: ProcessBlueprint; onClose: () => void }) {
  const preview = useBlueprintPreview(blueprint.id);
  const install = useInstallBlueprint();
  const [consented, setConsented] = useState(false);

  const data = preview.data;

  async function doInstall() {
    try {
      const res = await install.mutateAsync(blueprint.id);
      const counts = res.entity_ids.length + res.workflow_ids.length + res.rule_ids.length + res.report_ids.length;
      toast.success(`Installed “${blueprint.name}” (${counts} objects)`);
      onClose();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not install process");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{blueprint.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {blueprint.description && <p className="text-sm text-muted-foreground">{blueprint.description}</p>}

          {preview.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : preview.isError ? (
            <ErrorState title="Couldn't load preview" />
          ) : data ? (
            <>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
                {SUMMARY_LABELS.map(({ key, label }) => (
                  <div key={key} aria-label={label} className="rounded-md border p-2 text-center">
                    <div className="text-lg font-semibold tabular-nums">{data.summary[key]}</div>
                    <div className="text-xs text-muted-foreground">{label}</div>
                  </div>
                ))}
              </div>

              {!data.valid && (
                <div role="alert" className="space-y-1 rounded-md border border-destructive/40 p-2 text-xs text-destructive">
                  <p className="font-medium">This blueprint has manifest errors and can&apos;t be installed:</p>
                  {data.errors.map((e) => (
                    <p key={e}>{e}</p>
                  ))}
                </div>
              )}

              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={consented} onChange={(e) => setConsented(e.target.checked)} aria-label="Consent to install" />
                I understand this adds entities, workflows, rules, and reports to my workspace.
              </label>
            </>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={doInstall} disabled={!data?.valid || !consented || install.isPending}>
            {install.isPending ? "Installing…" : "Install process"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
