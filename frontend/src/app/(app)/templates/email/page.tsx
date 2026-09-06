"use client";

import { EmailTemplateBuilder } from "@/components/developer/email-template-builder";
import { TemplateNav } from "@/components/developer/template-nav";

export default function EmailTemplatesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Email templates</h1>
        <p className="text-sm text-muted-foreground">
          Locale-aware email content rendered and sent server-side.
        </p>
      </div>
      <TemplateNav />
      <EmailTemplateBuilder />
    </div>
  );
}
