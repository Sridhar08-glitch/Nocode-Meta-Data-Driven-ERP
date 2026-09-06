"use client";

import Link from "next/link";

import { ImportWizard } from "@/components/staging/import-wizard";

export default function ImportJobPage({ params }: { params: { id: string } }) {
  return (
    <div className="space-y-4">
      <Link href="/import" className="text-sm text-muted-foreground hover:underline">
        ← New import
      </Link>
      <ImportWizard jobId={params.id} />
    </div>
  );
}
