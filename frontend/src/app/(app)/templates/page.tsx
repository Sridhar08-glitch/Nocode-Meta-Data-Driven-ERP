"use client";

import { TemplateBuilder } from "@/components/notifications/template-builder";
import { TemplateNav } from "@/components/developer/template-nav";

export default function TemplatesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Notification templates</h1>
        <p className="text-sm text-muted-foreground">
          Reusable notification content with <code>{"${variables}"}</code>, previewed and test-sent
          before use.
        </p>
      </div>
      <TemplateNav />
      <TemplateBuilder />
    </div>
  );
}
