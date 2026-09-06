/**
 * Asset Management (EAM) client (Phase P2.9) — over `/api/v1/assets/` (backend live). HYBRID:
 * the asset master-data/operational entities (asset, asset_category, assignment, transfer,
 * maintenance, …) are framework metadata rendered by the generic F1.7 record runtime at
 * `/e/<entity_slug>`; this client only drives what the metadata runtime can't express:
 *   • asset lifecycle (create AST-numbered, assign/return/transfer/inspect/retire, complete work order)
 *   • the NATIVE depreciation engine (schedules, immutable runs, preview, run-all)
 *   • the NATIVE disposal engine (sale/scrap/donation/write-off with gain/loss)
 */
import { apiGet, apiSend } from "@/lib/api/request";

const A = "/api/v1/assets";

/** A created/updated asset metadata record (AST-numbered documents carry a `number`). */
export interface AssetRecord {
  id: string;
  number?: string;
  status?: string;
  [field: string]: unknown;
}

export type DepreciationMethod = "straight_line" | "declining_balance" | "double_declining";
export type ScheduleStatus = "active" | "fully_depreciated" | "disposed" | string;

export interface DepreciationSchedule {
  id: string;
  asset_record_id: string;
  method: DepreciationMethod;
  acquisition_cost: string;
  salvage_value: string;
  useful_life_months: number;
  start_date: string;
  status: ScheduleStatus;
}

export interface DepreciationEntry {
  id?: string;
  period_index: number;
  period_date?: string;
  amount: string;
  accumulated: string;
  net_book_value: string;
}

/** A previewed schedule row (computed, not persisted). */
export interface DepreciationPreviewRow {
  period_index: number;
  amount: string;
  accumulated: string;
  net_book_value: string;
}

export type DisposalMethod = "sale" | "scrap" | "donation" | "write_off";

export interface Disposal {
  id: string;
  asset_record_id: string;
  method: DisposalMethod;
  proceeds: string;
  book_value: string;
  gain_loss: string;
  reason: string;
  created_at?: string;
  [field: string]: unknown;
}

export const assetsApi = {
  /** Ensure the AST gapless number sequence exists (admin). */
  setup: () => apiSend<{ detail: string }>(`${A}/setup/`, "POST"),

  // ── asset lifecycle ──────────────────────────────────────────────────────────
  /** Create an asset; an AST `number` is auto-allocated server-side. Body = field-slug dict (name required). */
  createAsset: (data: Record<string, unknown>) => apiSend<AssetRecord>(`${A}/assets/`, "POST", data),

  /** Assign an asset to an employee / department / team (sets asset assigned + creates an assignment). */
  assignAsset: (recordId: string, data: { employee?: string; department?: string; team?: string }) =>
    apiSend<AssetRecord>(`${A}/assets/${recordId}/assign/`, "POST", data),

  /** Return an assigned asset (status→in_service). */
  returnAsset: (recordId: string) => apiSend<AssetRecord>(`${A}/assets/${recordId}/return/`, "POST"),

  /** Transfer an asset between locations/holders. */
  transferAsset: (
    recordId: string,
    data: { transfer_type: string; from_ref: string; to_ref: string },
  ) => apiSend<AssetRecord>(`${A}/assets/${recordId}/transfer/`, "POST", data),

  /** Record an inspection result against an asset. */
  inspectAsset: (
    recordId: string,
    data: { result: "passed" | "failed" | "requires_attention"; notes: string },
  ) => apiSend<AssetRecord>(`${A}/assets/${recordId}/inspect/`, "POST", data),

  /** Retire an asset (admin) — returns a disposal/retirement record. */
  retireAsset: (recordId: string, data: { reason: string; residual_value: string }) =>
    apiSend<Disposal>(`${A}/assets/${recordId}/retire/`, "POST", data),

  /** Mark a maintenance work order completed. */
  completeWorkOrder: (recordId: string) =>
    apiSend<AssetRecord>(`${A}/work-orders/${recordId}/complete/`, "POST"),

  // ── native depreciation engine ───────────────────────────────────────────────
  listSchedules: (assetRecordId?: string) =>
    apiGet<DepreciationSchedule[]>(
      `${A}/depreciation/schedules/${assetRecordId ? `?asset_record_id=${encodeURIComponent(assetRecordId)}` : ""}`,
    ),

  createSchedule: (data: {
    asset_record_id: string;
    method: DepreciationMethod;
    acquisition_cost: string;
    salvage_value: string;
    useful_life_months: number;
    start_date: string;
  }) => apiSend<DepreciationSchedule>(`${A}/depreciation/schedules/`, "POST", data),

  /** Post the next immutable depreciation entry for a schedule (or `{detail}` when fully depreciated). */
  runDepreciation: (scheduleId: string, periodDate: string) =>
    apiSend<DepreciationEntry & { detail?: string }>(
      `${A}/depreciation/schedules/${scheduleId}/run/`,
      "POST",
      { period_date: periodDate },
    ),

  scheduleEntries: (scheduleId: string) =>
    apiGet<DepreciationEntry[]>(`${A}/depreciation/schedules/${scheduleId}/entries/`),

  /** Post the next entry for every active schedule (admin). */
  runAllDepreciation: (periodDate: string) =>
    apiSend<{ posted: number }>(`${A}/depreciation/run-all/`, "POST", { period_date: periodDate }),

  /** Compute a full schedule without writing anything (preview aid). */
  previewDepreciation: (data: {
    method: DepreciationMethod;
    acquisition_cost: string;
    salvage_value: string;
    useful_life_months: number;
  }) => apiSend<DepreciationPreviewRow[]>(`${A}/depreciation/preview/`, "POST", data),

  // ── native disposal engine ───────────────────────────────────────────────────
  listDisposals: (assetRecordId?: string) =>
    apiGet<Disposal[]>(
      `${A}/disposals/list/${assetRecordId ? `?asset_record_id=${encodeURIComponent(assetRecordId)}` : ""}`,
    ),

  createDisposal: (data: {
    asset_record_id: string;
    method: DisposalMethod;
    proceeds: string;
    book_value?: string;
    reason: string;
  }) => apiSend<Disposal>(`${A}/disposals/`, "POST", data),
};

export { apiGet };
