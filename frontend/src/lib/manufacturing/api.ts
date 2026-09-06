/**
 * Manufacturing + MRP engine client (Phase P2.12) — a NATIVE engine over
 * `/api/v1/manufacturing/` (backend done). Work centers, BOMs (multi-level explode),
 * routings, production orders with a server-enforced lifecycle (release → issue →
 * complete → close), operations + OEE, MRP planning, standard costing, lot traceability
 * and quality (checks + NCRs). The heavy math (BOM explosion, inventory consumption →
 * WIP, GL posting, cost rollup, OEE, MRP netting) runs server-side; this client drives
 * the flows. Item references (product/component/warehouse) are raw Inventory Item ids.
 */
import { apiGet, apiSend } from "@/lib/api/request";

export type CenterType = "labor" | "machine" | "hybrid";
export type BomStatus = "draft" | "active" | "archived" | string;
export type OrderStatus =
  | "draft"
  | "planned"
  | "released"
  | "in_progress"
  | "completed"
  | "closed"
  | "cancelled";
export type MrpAction = "manufacture" | "purchase" | "none";

export interface WorkCenter {
  id: string;
  code: string;
  name: string;
  center_type: CenterType | string;
  capacity_per_hour: string;
  efficiency: string;
  cost_per_hour: string;
  is_active: boolean;
}

export interface BomComponent {
  id: string;
  bom_id: string;
  component_item_id: string;
  quantity: string;
  scrap_percent: string;
}

export interface Bom {
  id: string;
  number: string;
  product_item_id: string;
  quantity: string;
  revision: string;
  status: BomStatus;
}

export interface BomComponentInput {
  component_item_id: string;
  quantity: string;
  scrap_percent?: string;
}

export interface BomExplosion {
  requirements: Record<string, string>;
}

export interface Routing {
  id: string;
  product_item_id: string;
  name: string;
  status: string;
  [key: string]: unknown;
}

export interface RoutingStep {
  id: string;
  routing_id: string;
  work_center_id: string;
  sequence: number;
  name: string;
  setup_minutes: string;
  run_minutes: string;
  [key: string]: unknown;
}

export interface ProductionOrder {
  id: string;
  number: string;
  product_item_id: string;
  quantity: string;
  status: OrderStatus | string;
  material_cost: string;
  labor_cost: string;
  overhead_cost: string;
  total_cost: string;
  good_qty: string;
  bom_id?: string | null;
  routing_id?: string | null;
  warehouse_id?: string | null;
}

export interface Operation {
  id: string;
  production_order_id: string;
  work_center_id: string;
  sequence: number;
  name: string;
  status: string;
  labor_minutes: string;
  machine_minutes: string;
  downtime_minutes: string;
  good_qty: string;
  reject_qty: string;
}

export interface Reservation {
  id: string;
  production_order_id: string;
  component_item_id: string;
  quantity: string;
  status: string;
  [key: string]: unknown;
}

export interface OeeResult {
  availability: string;
  performance: string;
  quality: string;
  oee: string;
}

export interface MrpDemandRow {
  item_id: string;
  demand: string;
  available?: string;
}

export interface MrpResultRow {
  item_id: string;
  demand: string;
  available: string;
  net_requirement: string;
  suggested_qty: string;
  action: MrpAction | string;
}

export interface MrpRun {
  run_id: string;
  shortages: number;
  results: MrpResultRow[];
}

export interface StandardCost {
  material: string;
  labor: string;
  machine: string;
  overhead: string;
  total: string;
}

export interface LotTrace {
  lot: Record<string, unknown>;
  production_order: Record<string, unknown> | null;
  components: Record<string, unknown>[];
  consumed_lots: Record<string, unknown>[];
}

export interface QualityCheck {
  id: string;
  production_order_id: string;
  name: string;
  sampled_qty: string;
  passed_qty: string;
  failed_qty: string;
  [key: string]: unknown;
}

export interface Ncr {
  id: string;
  production_order_id: string;
  defect: string;
  [key: string]: unknown;
}

const M = "/api/v1/manufacturing";

function qs(params: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const manufacturingApi = {
  // setup
  setup: () => apiSend<{ detail: string }>(`${M}/setup/`, "POST", {}),

  // work centers
  listWorkCenters: () => apiGet<WorkCenter[]>(`${M}/work-centers/`),
  createWorkCenter: (data: Record<string, unknown>) =>
    apiSend<WorkCenter>(`${M}/work-centers/`, "POST", data),

  // BOMs
  listBoms: (productItemId?: string) =>
    apiGet<Bom[]>(`${M}/boms/${qs({ product_item_id: productItemId })}`),
  createBom: (data: {
    product_item_id: string;
    quantity: string;
    revision: string;
    components: BomComponentInput[];
  }) => apiSend<Bom>(`${M}/boms/`, "POST", data),
  approveBom: (id: string) => apiSend<Bom>(`${M}/boms/${id}/approve/`, "POST", {}),
  explodeBom: (productItemId: string, quantity: string) =>
    apiGet<BomExplosion>(
      `${M}/boms/explode/${qs({ product_item_id: productItemId, quantity })}`,
    ),
  listComponents: (bomId: string) =>
    apiGet<BomComponent[]>(`${M}/components/${qs({ bom_id: bomId })}`),
  createComponent: (data: Record<string, unknown>) =>
    apiSend<BomComponent>(`${M}/components/`, "POST", data),

  // routings
  listRoutings: (productItemId?: string) =>
    apiGet<Routing[]>(`${M}/routings/${qs({ product_item_id: productItemId })}`),
  createRouting: (data: Record<string, unknown>) =>
    apiSend<Routing>(`${M}/routings/`, "POST", data),
  listRoutingSteps: (routingId: string) =>
    apiGet<RoutingStep[]>(`${M}/routing-steps/${qs({ routing_id: routingId })}`),
  createRoutingStep: (data: Record<string, unknown>) =>
    apiSend<RoutingStep>(`${M}/routing-steps/`, "POST", data),

  // production orders + lifecycle
  listOrders: (status?: string) =>
    apiGet<ProductionOrder[]>(`${M}/orders/${qs({ status })}`),
  createOrder: (data: {
    product_item_id: string;
    quantity: string;
    bom_id?: string;
    routing_id?: string;
    warehouse_id?: string;
  }) => apiSend<ProductionOrder>(`${M}/orders/create/`, "POST", data),
  releaseOrder: (id: string) =>
    apiSend<ProductionOrder>(`${M}/orders/${id}/release/`, "POST", {}),
  issueOrder: (id: string) =>
    apiSend<ProductionOrder>(`${M}/orders/${id}/issue/`, "POST", {}),
  completeOrder: (
    id: string,
    data: { good_qty: string; overhead_percent?: string; lot_number?: string },
  ) => apiSend<ProductionOrder>(`${M}/orders/${id}/complete/`, "POST", data),
  closeOrder: (id: string) =>
    apiSend<ProductionOrder>(`${M}/orders/${id}/close/`, "POST", {}),
  orderOee: (id: string) => apiGet<OeeResult>(`${M}/orders/${id}/oee/`),

  // operations
  listOperations: (productionOrderId: string) =>
    apiGet<Operation[]>(`${M}/operations/${qs({ production_order_id: productionOrderId })}`),
  createOperation: (data: Record<string, unknown>) =>
    apiSend<Operation>(`${M}/operations/`, "POST", data),
  completeOperation: (
    id: string,
    data: {
      labor_minutes: string;
      machine_minutes: string;
      downtime_minutes: string;
      good_qty: string;
      reject_qty: string;
    },
  ) => apiSend<Operation>(`${M}/operations/${id}/complete/`, "POST", data),

  // reservations
  listReservations: (productionOrderId: string) =>
    apiGet<Reservation[]>(`${M}/reservations/${qs({ production_order_id: productionOrderId })}`),

  // MRP
  runMrp: (demand: MrpDemandRow[]) =>
    apiSend<MrpRun>(`${M}/mrp/run/`, "POST", { demand }),

  // standard costing
  standardCost: (params: {
    product_item_id: string;
    quantity: string;
    labor_minutes?: string;
    labor_rate_per_hour?: string;
    overhead_percent?: string;
  }) => apiGet<StandardCost>(`${M}/costing/standard/${qs(params)}`),

  // lots + quality
  traceLot: (lotId: string) => apiGet<LotTrace>(`${M}/lots/${lotId}/trace/`),
  createQualityCheck: (data: {
    production_order_id: string;
    name: string;
    sampled_qty: string;
    passed_qty: string;
    failed_qty: string;
  }) => apiSend<QualityCheck>(`${M}/quality-checks/`, "POST", data),
  createNcr: (data: { production_order_id: string; defect: string }) =>
    apiSend<Ncr>(`${M}/ncrs/`, "POST", data),
};
