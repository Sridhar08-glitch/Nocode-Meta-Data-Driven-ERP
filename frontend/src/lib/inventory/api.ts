/**
 * Inventory Engine client (Phase P2.4) — master data, stock transactions, and reports over
 * `/api/v1/inventory/` (backend P2.4). Costing (FIFO / weighted-average) and race-safe stock
 * math are enforced server-side; this client submits transactions and renders balances/movements.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type ValuationMethod = "fifo" | "average" | "standard";
export type MovementType = "receipt" | "issue" | "adjustment" | "transfer_in" | "transfer_out";

export interface Item {
  id: string;
  sku: string;
  name: string;
  category: string | null;
  uom: string;
  valuation_method: ValuationMethod;
  standard_cost: string;
  track_inventory: boolean;
  is_active: boolean;
  inventory_account_code: string;
  cogs_account_code: string;
  description: string;
  created_at: string;
  updated_at: string;
}
export interface Warehouse {
  id: string; code: string; name: string; is_active: boolean; created_at: string; updated_at: string;
}
export interface ItemCategory {
  id: string; name: string; parent: string | null; description: string;
}
export interface StockMovement {
  id: string; item: string; sku: string; warehouse: string; warehouse_code: string;
  location: string | null; movement_type: MovementType; quantity: string; unit_cost: string;
  total_cost: string; on_hand_after: string; occurred_at: string; reference: string;
  memo: string; journal_entry_id: string | null; created_at: string;
}
export interface StockBalanceRow {
  item_id: string; sku: string; item_name: string; warehouse_id: string; warehouse_code: string;
  on_hand: string; avg_cost: string; value: string;
}

const I = "/api/v1/inventory";

export const inventoryApi = {
  // master data
  listItems: () => apiGet<Item[]>(`${I}/items/`),
  createItem: (data: Partial<Item>) => apiSend<Item>(`${I}/items/`, "POST", data),
  updateItem: (id: string, data: Partial<Item>) => apiSend<Item>(`${I}/items/${id}/`, "PATCH", data),
  deleteItem: (id: string) => apiSend<void>(`${I}/items/${id}/`, "DELETE"),
  listWarehouses: () => apiGet<Warehouse[]>(`${I}/warehouses/`),
  createWarehouse: (data: Partial<Warehouse>) => apiSend<Warehouse>(`${I}/warehouses/`, "POST", data),
  deleteWarehouse: (id: string) => apiSend<void>(`${I}/warehouses/${id}/`, "DELETE"),
  listCategories: () => apiGet<ItemCategory[]>(`${I}/categories/`),
  // transactions
  receive: (data: Record<string, unknown>) => apiSend<StockMovement>(`${I}/receive/`, "POST", data),
  issue: (data: Record<string, unknown>) => apiSend<StockMovement>(`${I}/issue/`, "POST", data),
  adjust: (data: Record<string, unknown>) => apiSend<StockMovement>(`${I}/adjust/`, "POST", data),
  transfer: (data: Record<string, unknown>) =>
    apiSend<{ out: StockMovement; in: StockMovement }>(`${I}/transfer/`, "POST", data),
  // reports
  stock: (params?: { warehouse?: string; item?: string }) => {
    const q = new URLSearchParams(params as Record<string, string>);
    const qs = q.toString();
    return apiGet<{ rows: StockBalanceRow[] }>(`${I}/stock/${qs ? `?${qs}` : ""}`);
  },
  valuation: (warehouse?: string) =>
    apiGet<{ rows: StockBalanceRow[]; total_value: string }>(`${I}/valuation/${warehouse ? `?warehouse=${warehouse}` : ""}`),
  movements: (params?: { item?: string; warehouse?: string }) => {
    const q = new URLSearchParams(params as Record<string, string>);
    const qs = q.toString();
    return apiGet<{ rows: StockMovement[] }>(`${I}/movements/${qs ? `?${qs}` : ""}`);
  },
};
