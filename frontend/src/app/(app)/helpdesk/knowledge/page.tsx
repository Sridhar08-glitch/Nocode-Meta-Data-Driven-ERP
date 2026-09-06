"use client";

import { HelpdeskNav } from "@/components/helpdesk/helpdesk-nav";
import { KnowledgePanel } from "@/components/helpdesk/knowledge-panel";

export default function HelpdeskKnowledgePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Knowledge recommendation</h1>
        <p className="text-sm text-muted-foreground">
          Recommend knowledge-base articles for a ticket by deterministic keyword and/or category match.
          The matching runs server-side and is fully deterministic — there is no AI.
        </p>
      </div>
      <HelpdeskNav />
      <KnowledgePanel />
    </div>
  );
}
