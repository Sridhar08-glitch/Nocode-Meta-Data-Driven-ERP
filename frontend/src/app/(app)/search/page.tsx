"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/states";
import { useSearch } from "@/lib/search/hooks";

export default function SearchPage() {
  const router = useRouter();
  const initial = useSearchParams().get("q") ?? "";
  const [q, setQ] = useState(initial);
  const search = useSearch(q, { limit: 50 });
  const results = search.data?.results ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Search</h1>
        <p className="text-sm text-muted-foreground">Find records across every entity in your workspace.</p>
      </div>
      <Input aria-label="Search query" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" autoFocus />

      {q.trim().length < 2 && <p className="text-sm text-muted-foreground">Type at least 2 characters.</p>}
      {search.isLoading && <Skeleton className="h-40 w-full" />}
      {search.data && results.length === 0 && q.trim().length >= 2 && <EmptyState title="No results" />}

      {results.length > 0 && (
        <>
          <p className="text-sm text-muted-foreground">{search.data?.total} results</p>
          <ul className="space-y-2">
            {results.map((r) => (
              <li key={`${r.entity_slug}/${r.record_id}`} className="rounded-md border p-3">
                <button
                  className="flex w-full items-center gap-2 text-left hover:underline"
                  onClick={() => router.push(`/e/${r.entity_slug}/${r.record_id}`)}
                >
                  <span className="font-medium">{r.title || r.record_id}</span>
                  <Badge variant="outline">{r.entity_slug}</Badge>
                </button>
                {r.snippet && r.snippet !== r.title && (
                  <p className="mt-1 truncate text-sm text-muted-foreground">{r.snippet}</p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
