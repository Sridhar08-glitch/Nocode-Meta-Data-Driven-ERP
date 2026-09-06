"use client";

import { useMemo, useState } from "react";

import { QueryBuilder, type FieldOption } from "@/components/nql/query-builder";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/lib/api/errors";
import { useFields } from "@/lib/metadata/builder-hooks";
import { useEntities } from "@/lib/metadata/hooks";
import { emptyQuery } from "@/lib/nql/builder";
import { useRunNql } from "@/lib/nql/hooks";
import type { NqlQuery } from "@/lib/nql/types";

/** NQL Query Builder playground (Phase F1.9) — pick an entity, build a query, run it live. */
export default function QueryPage() {
  const entities = useEntities();
  const [entitySlug, setEntitySlug] = useState<string>("");
  const [query, setQuery] = useState<NqlQuery | null>(null);
  const fields = useFields(entitySlug);
  const run = useRunNql();

  const fieldOptions: FieldOption[] = useMemo(
    () => (fields.data ?? []).map((f) => ({ slug: f.slug, name: f.name })),
    [fields.data],
  );

  function selectEntity(slug: string) {
    setEntitySlug(slug);
    setQuery(emptyQuery(slug));
    run.reset();
  }

  async function execute() {
    if (!query) return;
    try {
      await run.mutateAsync(query);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Query failed");
    }
  }

  const columns = run.data?.rows.length ? Object.keys(run.data.rows[0]) : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Query builder</h1>
        <p className="text-sm text-muted-foreground">
          Build a query visually, preview the NQL, and run it against your data.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="query-entity">Entity</Label>
        {entities.isLoading ? (
          <Skeleton className="h-9 w-56" />
        ) : entities.isError ? (
          <ErrorState title="Couldn't load entities" />
        ) : (
          <Select value={entitySlug || undefined} onValueChange={selectEntity}>
            <SelectTrigger id="query-entity" className="w-56">
              <SelectValue placeholder="Pick an entity" />
            </SelectTrigger>
            <SelectContent>
              {(entities.data ?? []).map((e) => (
                <SelectItem key={e.id} value={e.slug}>
                  {e.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {query && (
        <>
          <QueryBuilder fields={fieldOptions} value={query} onChange={setQuery} />
          <Button onClick={execute} disabled={run.isPending}>
            {run.isPending ? "Running…" : "Run query"}
          </Button>

          {run.isSuccess && (
            <section className="space-y-2">
              <h3 className="text-sm font-medium text-muted-foreground">{run.data.count} rows</h3>
              {run.data.rows.length === 0 ? (
                <EmptyState title="No matching rows" />
              ) : (
                <div className="overflow-x-auto rounded-md border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        {columns.map((c) => (
                          <th key={c} className="px-3 py-2 text-left font-medium">
                            {c}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {run.data.rows.map((row, i) => (
                        <tr key={i} className="border-t">
                          {columns.map((c) => (
                            <td key={c} className="px-3 py-2">
                              {row[c] === null || row[c] === undefined ? "—" : String(row[c])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </>
      )}

      {!query && !entities.isLoading && !entities.isError && (
        <EmptyState title="Pick an entity" description="Choose an entity to start building a query." />
      )}
    </div>
  );
}
