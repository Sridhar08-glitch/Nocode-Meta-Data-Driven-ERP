"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";
import type { KnowledgeArticleHit } from "@/lib/helpdesk/api";
import { useKnowledgeRecommend } from "@/lib/helpdesk/hooks";

/** Native knowledge-recommendation panel (Phase P2.11) — enter a category and/or keywords, then view the
 * deterministic keyword/category article matches with a relevance score. The matching is server-side and
 * deterministic (NO AI). */
export function KnowledgePanel() {
  const [category, setCategory] = useState("");
  const [keywords, setKeywords] = useState("");
  const [active, setActive] = useState<{ category?: string; q?: string } | null>(null);

  function search() {
    const c = category.trim();
    const q = keywords.trim();
    if (!c && !q) return;
    setActive({ category: c || undefined, q: q || undefined });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-2 rounded-lg border p-4">
        <label className="w-48 space-y-1">
          <span className="text-xs font-medium">Category</span>
          <Input
            aria-label="Category"
            placeholder="e.g. billing"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
        </label>
        <label className="flex-1 space-y-1">
          <span className="text-xs font-medium">Keywords</span>
          <Input
            aria-label="Keywords"
            placeholder="login error reset password"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
          />
        </label>
        <Button onClick={search} disabled={!category.trim() && !keywords.trim()}>
          Recommend
        </Button>
      </div>

      {!active ? (
        <EmptyState
          title="Enter a category or keywords"
          description="Recommend knowledge-base articles by deterministic keyword/category match (no AI)."
        />
      ) : (
        <Results params={active} />
      )}
    </div>
  );
}

export function Results({ params }: { params: { category?: string; q?: string } }) {
  const rec = useKnowledgeRecommend(params, true);

  if (rec.isLoading) return <Skeleton className="h-40 w-full" />;
  if (rec.isError) return <ErrorState title="Couldn't load recommendations" />;

  const hits = rec.data ?? [];
  if (hits.length === 0) {
    return <EmptyState title="No matching articles" description="Try a different category or keywords." />;
  }

  return (
    <section className="space-y-2">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {hits.length} recommended article{hits.length === 1 ? "" : "s"}
      </h2>
      <ul className="space-y-2">
        {hits.map((a: KnowledgeArticleHit) => (
          <li key={a.id} className="flex items-center justify-between gap-3 rounded-lg border p-4">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{a.title}</p>
              <p className="text-xs text-muted-foreground">{a.category}</p>
            </div>
            <Badge variant="secondary" className="font-mono">
              {a.score}
            </Badge>
          </li>
        ))}
      </ul>
    </section>
  );
}
