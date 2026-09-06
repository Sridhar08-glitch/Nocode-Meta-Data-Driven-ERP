"use client";

import { CrmOverview } from "@/components/crm/crm-overview";

/**
 * CRM Solution overview (Phase P2.6). The generic metadata runtime renders leads/accounts/contacts/
 * opportunities/activities CRUD; this page exposes the CRM pipeline lifecycle actions that runtime
 * can't express (qualify a lead, win/lose an opportunity, complete an activity).
 */
export default function CrmPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">CRM</h1>
        <p className="text-sm text-muted-foreground">
          Lead-to-close sales pipeline: leads, accounts, contacts, opportunities, and activities.
          Qualifying a lead opens a numbered opportunity; winning or losing it closes the deal.
        </p>
      </div>
      <CrmOverview />
    </div>
  );
}
