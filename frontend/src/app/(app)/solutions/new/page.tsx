"use client";

import Link from "next/link";

import { CreateSolutionWizard } from "@/components/solution-templates/create-solution-wizard";
import { Button } from "@/components/ui/button";

export default function CreateSolutionPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Create a solution</h1>
          <p className="text-sm text-muted-foreground">
            Compose a complete ERP solution from library building blocks, preview the manifest, then
            provision it into your workspace.
          </p>
        </div>
        <Button asChild variant="ghost">
          <Link href="/solutions">Back to solutions</Link>
        </Button>
      </div>
      <CreateSolutionWizard />
    </div>
  );
}
