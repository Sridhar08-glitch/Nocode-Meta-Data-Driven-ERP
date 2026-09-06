"use client";

import { useParams } from "next/navigation";

import { PortalShell } from "@/components/portal/portal-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { usePortalRecords } from "@/lib/portal/hooks";

/** Portal scoped record list — the server returns ONLY records linked to this portal user. */
export default function PortalEntityPage() {
  return (
    <PortalShell>
      <EntityRecords />
    </PortalShell>
  );
}

function EntityRecords() {
  const params = useParams<{ entity: string }>();
  const entity = params.entity;
  const records = usePortalRecords(entity);

  if (records.isLoading) return <Skeleton className="h-64 w-full" />;
  if (records.isError) return <ErrorState title="Couldn't load records" description="You may not have access to this entity." />;
  const rows = records.data?.results ?? [];

  if (rows.length === 0) {
    return <EmptyState title="Nothing here yet" description="No records are linked to your account." />;
  }

  // derive columns from the first row (excluding internal keys)
  const cols = Object.keys(rows[0]).filter((k) => k !== "id" && !k.startsWith("_")).slice(0, 6);

  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold capitalize">{entity}</h1>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {cols.map((c) => (
                <TableHead key={c} className="capitalize">{c.replace(/_/g, " ")}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.id}>
                {cols.map((c) => (
                  <TableCell key={c}>{formatCell(r[c])}</TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
