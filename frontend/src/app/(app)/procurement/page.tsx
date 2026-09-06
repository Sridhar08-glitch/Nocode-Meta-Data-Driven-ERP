"use client";

import { ProcurementOverview } from "@/components/procurement/procurement-overview";

/**
 * Procurement Solution overview (Phase P2.5). The generic metadata runtime renders vendors/RFQs/POs/
 * receipts/bills CRUD; this page exposes the procurement lifecycle actions that runtime can't express.
 */
export default function ProcurementPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Procurement</h1>
        <p className="text-sm text-muted-foreground">
          Vendor-to-bill procurement: RFQs, purchase orders, goods receipts, and vendor bills.
          Numbered documents are gapless; posting a receipt updates stock and posting a bill hits the ledger.
        </p>
      </div>
      <ProcurementOverview />
    </div>
  );
}
