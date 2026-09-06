"use client";

import { PublicFormsAdmin } from "@/components/public-forms/public-forms-admin";

export default function PublicFormsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Public forms</h1>
        <p className="text-sm text-muted-foreground">
          Publish forms for unauthenticated submission, then review, approve, or reject incoming entries.
        </p>
      </div>
      <PublicFormsAdmin />
    </div>
  );
}
