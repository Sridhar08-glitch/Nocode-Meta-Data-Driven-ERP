"use client";

import { ProcessCatalog } from "@/components/process-catalog/process-catalog";

export default function CatalogPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Process catalog</h1>
        <p className="text-sm text-muted-foreground">
          Install packaged business processes — entities, workflows, rules, and reports — into your
          workspace.
        </p>
      </div>
      <ProcessCatalog />
    </div>
  );
}
