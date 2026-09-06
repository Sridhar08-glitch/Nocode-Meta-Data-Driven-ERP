"use client";

import { HelpdeskNav } from "@/components/helpdesk/helpdesk-nav";
import { HelpdeskOverview } from "@/components/helpdesk/helpdesk-overview";

/**
 * Helpdesk + ITSM overview (Phase P2.11). HYBRID solution: the generic metadata runtime renders the
 * service-desk, ITSM, knowledge, customer, and field/agent entity CRUD; this page ties them together with
 * module-grouped links, the native knowledge-recommendation + SLA-dashboard engines, and the ticket
 * lifecycle actions (assign / auto-assign / escalate / set status / resolve / close / CSAT, approve
 * change) that runtime can't express.
 */
export default function HelpdeskPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Helpdesk &amp; ITSM</h1>
        <p className="text-sm text-muted-foreground">
          Service desk, ITSM (problems, changes, major incidents), knowledge base, service contracts &amp;
          CSAT, and field service, plus the native ticket lifecycle, auto-assignment, escalation,
          knowledge recommendation, CSAT, and SLA engines. Helpdesk documents are rendered by the generic
          record runtime; lifecycle, knowledge, and SLA are driven here.
        </p>
      </div>
      <HelpdeskNav />
      <HelpdeskOverview />
    </div>
  );
}
