/**
 * Procurement Solution client (Phase P2.5) — the procurement lifecycle actions the generic
 * metadata runtime can't express, over `/api/v1/procurement/` (backend live). The solution's
 * vendors/RFQs/POs/receipts/bills CRUD is rendered by the generic F1.7 record runtime at
 * `/e/<entity_slug>`; this client only drives setup + document numbering + approve/post actions.
 */
import { apiGet, apiSend } from "@/lib/api/request";

/** Procurement document entity slugs (provisioned by the Procurement solution template). */
export type ProcurementEntitySlug =
  | "vendor"
  | "vendor_contact"
  | "rfq"
  | "rfq_line"
  | "purchase_order"
  | "purchase_order_line"
  | "goods_receipt"
  | "goods_receipt_line"
  | "vendor_bill"
  | "vendor_bill_line";

/** A created/updated procurement record. Numbered documents carry an allocated `number`. */
export interface ProcurementRecord {
  id: string;
  number?: string;
  status?: string;
  [field: string]: unknown;
}

const P = "/api/v1/procurement";

export const procurementApi = {
  /** Ensure RFQ/PO/GR/VB gapless number sequences exist (admin). */
  setup: () => apiSend<{ detail: string }>(`${P}/setup/`, "POST"),

  /** Create a procurement document; numbered docs get a gapless `number` auto-allocated. */
  createDocument: (entitySlug: ProcurementEntitySlug, data: Record<string, unknown>) =>
    apiSend<ProcurementRecord>(`${P}/${entitySlug}/`, "POST", data),

  /** Set status=approved on a procurement document (RFQ / PO / bill). */
  approveDocument: (entitySlug: ProcurementEntitySlug, recordId: string) =>
    apiSend<ProcurementRecord>(`${P}/${entitySlug}/${recordId}/approve/`, "POST"),

  /** Post a goods receipt into the Inventory ledger (increases stock per line). Idempotent. */
  postGoodsReceipt: (recordId: string) =>
    apiSend<ProcurementRecord>(`${P}/goods-receipts/${recordId}/post/`, "POST"),

  /** Post a vendor bill (emits a GL event). Idempotent. */
  postVendorBill: (recordId: string) =>
    apiSend<ProcurementRecord>(`${P}/vendor-bills/${recordId}/post/`, "POST"),
};

/** Re-export so callers can import the GET helper consistently if needed later. */
export { apiGet };
