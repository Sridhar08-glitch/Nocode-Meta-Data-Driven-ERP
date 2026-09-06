"use client";

import Link from "next/link";

import { SolutionCatalog } from "@/components/solution-templates/solution-catalog";
import { Button } from "@/components/ui/button";

export default function SolutionsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Solutions</h1>
          <p className="text-sm text-muted-foreground">
            Install curated end-to-end solution templates — entities, forms, views, workflows, rules,
            reports, and apps — into your workspace with one click.
          </p>
        </div>
        <Button asChild>
          <Link href="/solutions/new">Create solution</Link>
        </Button>
      </div>
      <SolutionCatalog />
    </div>
  );
}
