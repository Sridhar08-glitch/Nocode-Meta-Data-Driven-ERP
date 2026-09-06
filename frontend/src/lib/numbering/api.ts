/**
 * Numbering Engine client (Phase P2.1) — gapless document-number sequences over
 * `/api/v1/numbering/` (backend P2.1). Sequence definitions are owner/admin-managed; any
 * member may peek/allocate. Other engines call the backend service directly, not this API.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type ResetScope = "never" | "yearly" | "monthly" | "daily";

export interface NumberSequence {
  id: string;
  key: string;
  name: string;
  description: string;
  prefix: string;
  suffix: string;
  padding: number;
  start_value: number;
  increment: number;
  reset_scope: ResetScope;
  include_period_in_format: boolean;
  current_value: number;
  period_key: string;
  is_active: boolean;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}
export interface NumberSequenceWrite {
  key: string;
  name?: string;
  description?: string;
  prefix?: string;
  suffix?: string;
  padding?: number;
  start_value?: number;
  increment?: number;
  reset_scope?: ResetScope;
  include_period_in_format?: boolean;
  is_active?: boolean;
}
export interface NumberAllocation {
  id: string;
  sequence: string;
  key: string;
  formatted: string;
  value: number;
  period_key: string;
  context: Record<string, unknown>;
  allocated_by: string | null;
  created_at: string;
}

const N = "/api/v1/numbering";

export const numberingApi = {
  list: () => apiGet<NumberSequence[]>(`${N}/sequences/`),
  create: (data: NumberSequenceWrite) => apiSend<NumberSequence>(`${N}/sequences/`, "POST", data),
  update: (id: string, data: Partial<NumberSequenceWrite>) =>
    apiSend<NumberSequence>(`${N}/sequences/${id}/`, "PATCH", data),
  remove: (id: string) => apiSend<void>(`${N}/sequences/${id}/`, "DELETE"),
  peek: (id: string) => apiGet<{ next: string }>(`${N}/sequences/${id}/peek/`),
  allocate: (id: string) => apiSend<{ formatted: string }>(`${N}/sequences/${id}/allocate/`, "POST", {}),
  reset: (id: string) => apiSend<NumberSequence>(`${N}/sequences/${id}/reset/`, "POST", {}),
  allocations: (id: string) =>
    apiGet<{ results: NumberAllocation[] }>(`${N}/sequences/${id}/allocations/`),
};
