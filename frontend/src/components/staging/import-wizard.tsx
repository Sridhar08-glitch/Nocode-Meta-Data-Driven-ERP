"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { useFields } from "@/lib/metadata/builder-hooks";
import { useConfirmImport, useImportJob, useImportPreview, useSetImportMapping } from "@/lib/staging/hooks";

const SKIP = "__skip__";

const STEPS: { key: string; label: string; statuses: string[] }[] = [
  { key: "parse", label: "Parsing", statuses: ["uploading", "parsing"] },
  { key: "validate", label: "Validating", statuses: ["validating"] },
  { key: "review", label: "Review", statuses: ["awaiting_confirm"] },
  { key: "import", label: "Importing", statuses: ["importing"] },
  { key: "done", label: "Done", statuses: ["completed", "failed", "cancelled"] },
];

/** Import wizard runtime (Phase F2.6): polls the job, shows the validation report, confirms import. */
export function ImportWizard({ jobId }: { jobId: string }) {
  const job = useImportJob(jobId);
  const data = job.data;
  const reviewing = data?.status === "awaiting_confirm";
  const preview = useImportPreview(jobId, !!reviewing);
  const confirm = useConfirmImport(jobId);

  if (job.isLoading) return <Skeleton className="h-64 w-full" />;
  if (job.isError || !data) return <ErrorState title="Import job not found" />;

  const activeStep = STEPS.findIndex((s) => s.statuses.includes(data.status));

  async function runConfirm() {
    try {
      await confirm.mutateAsync();
      toast.success("Import started");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not start import");
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Import — {data.entity_slug}</h1>
        <p className="text-sm text-muted-foreground">{data.source_filename}</p>
      </div>

      <ol className="flex flex-wrap gap-2 text-sm">
        {STEPS.map((s, i) => (
          <li
            key={s.key}
            className={
              i === activeStep
                ? "rounded-full bg-primary px-3 py-1 text-primary-foreground"
                : i < activeStep
                  ? "rounded-full bg-muted px-3 py-1 text-foreground"
                  : "rounded-full border px-3 py-1 text-muted-foreground"
            }
          >
            {s.label}
          </li>
        ))}
      </ol>

      <div className="flex flex-wrap gap-4 text-sm">
        <Metric label="Total" value={data.total_rows} />
        <Metric label="Valid" value={data.valid_rows} />
        <Metric label="Invalid" value={data.invalid_rows} />
        {data.status === "completed" && <Metric label="Imported" value={data.imported_rows} />}
        {data.status === "completed" && <Metric label="Skipped" value={data.skipped_rows} />}
      </div>

      {data.error_message && <ErrorState title="Import error" description={data.error_message} />}

      {reviewing && <MappingEditor jobId={jobId} entitySlug={data.entity_slug} mapping={data.column_mapping} />}

      {reviewing && (
        <>
          <section aria-label="Validation preview" className="overflow-x-auto rounded-md border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-1 text-left">Row</th>
                  <th className="px-3 py-1 text-left">Status</th>
                  <th className="px-3 py-1 text-left">Issues</th>
                </tr>
              </thead>
              <tbody>
                {(preview.data?.results ?? []).map((r) => (
                  <tr key={r.id} className="border-b">
                    <td className="px-3 py-1 tabular-nums">{r.row_number}</td>
                    <td className="px-3 py-1">
                      <Badge variant={r.status === "invalid" ? "destructive" : "outline"}>{r.status}</Badge>
                    </td>
                    <td className="px-3 py-1 text-xs text-muted-foreground">
                      {r.validation_errors.map((e) => `${e.field || "row"}: ${e.message}`).join("; ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <Button onClick={runConfirm} disabled={confirm.isPending || data.valid_rows === 0}>
            {confirm.isPending ? "Starting…" : `Import ${data.valid_rows} valid rows`}
          </Button>
        </>
      )}

      {(data.status === "parsing" || data.status === "validating" || data.status === "importing") && (
        <p className="text-sm text-muted-foreground">Working… this page refreshes automatically.</p>
      )}
    </div>
  );
}

/** Manual column→field remap. Saving re-runs validation server-side. */
function MappingEditor({
  jobId,
  entitySlug,
  mapping,
}: {
  jobId: string;
  entitySlug: string;
  mapping: Record<string, string | null>;
}) {
  const fields = useFields(entitySlug);
  const save = useSetImportMapping(jobId);
  const [draft, setDraft] = useState<Record<string, string | null>>(mapping);
  const sourceColumns = Object.keys(mapping);
  if (sourceColumns.length === 0) return null;

  async function apply() {
    try {
      await save.mutateAsync(draft);
      toast.success("Mapping updated — re-validating");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not update mapping");
    }
  }

  return (
    <section aria-label="Column mapping" className="space-y-2 rounded-md border p-3">
      <h3 className="text-sm font-medium text-muted-foreground">Column mapping</h3>
      <div className="grid gap-2 sm:grid-cols-2">
        {sourceColumns.map((col) => (
          <label key={col} className="flex items-center gap-2 text-sm">
            <span className="w-32 shrink-0 truncate font-mono text-xs">{col}</span>
            <Select
              value={draft[col] ?? SKIP}
              onValueChange={(v) => setDraft((d) => ({ ...d, [col]: v === SKIP ? null : v }))}
            >
              <SelectTrigger aria-label={`Map ${col}`} className="h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={SKIP}>— Skip —</SelectItem>
                {(fields.data ?? []).map((f) => (
                  <SelectItem key={f.slug} value={f.slug}>
                    {f.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
        ))}
      </div>
      <Button size="sm" variant="outline" onClick={apply} disabled={save.isPending}>
        {save.isPending ? "Saving…" : "Save mapping & re-validate"}
      </Button>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border px-3 py-2 text-center">
      <div className="text-xl font-semibold tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
