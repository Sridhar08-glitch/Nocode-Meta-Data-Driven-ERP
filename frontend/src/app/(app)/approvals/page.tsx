"use client";

import { ApprovalBuilder } from "@/components/approvals/approval-builder";

export default function ApprovalsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Approvals</h1>
        <p className="text-sm text-muted-foreground">Multi-level approval matrices with quorum and timeouts.</p>
      </div>
      <ApprovalBuilder />
    </div>
  );
}
