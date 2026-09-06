"use client";

import { DocumentTemplateBuilder } from "@/components/developer/document-template-builder";
import { TemplateNav } from "@/components/developer/template-nav";

export default function DocumentTemplatesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Document templates</h1>
        <p className="text-sm text-muted-foreground">
          Entity-bound templates rendered to PDF on the server.
        </p>
      </div>
      <TemplateNav />
      <DocumentTemplateBuilder />
    </div>
  );
}
