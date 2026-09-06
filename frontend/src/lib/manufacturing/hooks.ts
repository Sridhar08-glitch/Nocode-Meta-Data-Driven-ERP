"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import {
  type BomComponentInput,
  type MrpDemandRow,
  manufacturingApi,
} from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    qc,
    enabled: isReady && !!ws,
    /** Invalidate the whole manufacturing cache for this workspace. */
    invalidate: () => qc.invalidateQueries({ queryKey: ["manufacturing", ws] }),
  };
}

/** Whether the caller may run privileged manufacturing writes (server gates regardless). */
export function useCanManageManufacturing(): boolean {
  const { workspace } = useTenant();
  const role = workspace?.role;
  return role === "owner" || role === "admin";
}

// ── setup ─────────────────────────────────────────────────────────────────────
export function useRunSetup() {
  return useMutation({ mutationFn: () => manufacturingApi.setup() });
}

// ── work centers ────────────────────────────────────────────────────────────
export function useWorkCenters() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "work-centers", ws],
    queryFn: () => manufacturingApi.listWorkCenters(),
    enabled,
    staleTime: 60_000,
  });
}
export function useCreateWorkCenter() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => manufacturingApi.createWorkCenter(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["manufacturing", "work-centers", ws] }),
  });
}

// ── BOMs ──────────────────────────────────────────────────────────────────────
export function useBoms(productItemId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "boms", ws, productItemId ?? null],
    queryFn: () => manufacturingApi.listBoms(productItemId),
    enabled,
    staleTime: 30_000,
  });
}
export function useCreateBom() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: {
      product_item_id: string;
      quantity: string;
      revision: string;
      components: BomComponentInput[];
    }) => manufacturingApi.createBom(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["manufacturing", "boms", ws], exact: false }),
  });
}
export function useApproveBom() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (id: string) => manufacturingApi.approveBom(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["manufacturing", "boms", ws], exact: false }),
  });
}
export function useExplodeBom(productItemId: string | undefined, quantity: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "boms", ws, "explode", productItemId, quantity],
    queryFn: () => manufacturingApi.explodeBom(productItemId as string, quantity),
    enabled: enabled && !!productItemId && !!quantity,
  });
}
export function useBomComponents(bomId: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "components", ws, bomId],
    queryFn: () => manufacturingApi.listComponents(bomId as string),
    enabled: enabled && !!bomId,
  });
}

// ── routings ──────────────────────────────────────────────────────────────────
export function useRoutings(productItemId?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "routings", ws, productItemId ?? null],
    queryFn: () => manufacturingApi.listRoutings(productItemId),
    enabled,
    staleTime: 30_000,
  });
}
export function useCreateRouting() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => manufacturingApi.createRouting(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["manufacturing", "routings", ws], exact: false }),
  });
}
export function useRoutingSteps(routingId: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "routing-steps", ws, routingId],
    queryFn: () => manufacturingApi.listRoutingSteps(routingId as string),
    enabled: enabled && !!routingId,
  });
}
export function useCreateRoutingStep(routingId: string) {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => manufacturingApi.createRoutingStep(data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["manufacturing", "routing-steps", ws, routingId] }),
  });
}

// ── production orders + lifecycle ───────────────────────────────────────────────
export function useOrders(status?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "orders", ws, status ?? null],
    queryFn: () => manufacturingApi.listOrders(status),
    enabled,
    staleTime: 15_000,
  });
}
export function useCreateOrder() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (data: {
      product_item_id: string;
      quantity: string;
      bom_id?: string;
      routing_id?: string;
      warehouse_id?: string;
    }) => manufacturingApi.createOrder(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["manufacturing", "orders", ws], exact: false }),
  });
}

/** An order lifecycle transition — invalidates orders, reservations and operations. */
function useOrderTransition(fn: (id: string) => Promise<unknown>) {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (id: string) => fn(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["manufacturing", "orders", ws], exact: false });
      qc.invalidateQueries({ queryKey: ["manufacturing", "reservations", ws], exact: false });
      qc.invalidateQueries({ queryKey: ["manufacturing", "operations", ws], exact: false });
    },
  });
}
export const useReleaseOrder = () => useOrderTransition((id) => manufacturingApi.releaseOrder(id));
export const useIssueOrder = () => useOrderTransition((id) => manufacturingApi.issueOrder(id));
export const useCloseOrder = () => useOrderTransition((id) => manufacturingApi.closeOrder(id));

export function useCompleteOrder() {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (vars: {
      id: string;
      good_qty: string;
      overhead_percent?: string;
      lot_number?: string;
    }) =>
      manufacturingApi.completeOrder(vars.id, {
        good_qty: vars.good_qty,
        overhead_percent: vars.overhead_percent,
        lot_number: vars.lot_number,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["manufacturing", "orders", ws], exact: false });
      qc.invalidateQueries({ queryKey: ["manufacturing", "operations", ws], exact: false });
    },
  });
}

export function useOrderOee(id: string | undefined, enabled = true) {
  const { ws, enabled: scopeEnabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "orders", ws, "oee", id],
    queryFn: () => manufacturingApi.orderOee(id as string),
    enabled: scopeEnabled && enabled && !!id,
  });
}

// ── operations ──────────────────────────────────────────────────────────────
export function useOperations(productionOrderId: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "operations", ws, productionOrderId],
    queryFn: () => manufacturingApi.listOperations(productionOrderId as string),
    enabled: enabled && !!productionOrderId,
  });
}
export function useCompleteOperation(productionOrderId: string) {
  const { qc, ws } = useScope();
  return useMutation({
    mutationFn: (vars: {
      id: string;
      labor_minutes: string;
      machine_minutes: string;
      downtime_minutes: string;
      good_qty: string;
      reject_qty: string;
    }) =>
      manufacturingApi.completeOperation(vars.id, {
        labor_minutes: vars.labor_minutes,
        machine_minutes: vars.machine_minutes,
        downtime_minutes: vars.downtime_minutes,
        good_qty: vars.good_qty,
        reject_qty: vars.reject_qty,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["manufacturing", "operations", ws, productionOrderId] });
      qc.invalidateQueries({ queryKey: ["manufacturing", "orders", ws], exact: false });
    },
  });
}

// ── reservations ────────────────────────────────────────────────────────────
export function useReservations(productionOrderId: string | undefined) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "reservations", ws, productionOrderId],
    queryFn: () => manufacturingApi.listReservations(productionOrderId as string),
    enabled: enabled && !!productionOrderId,
  });
}

// ── MRP ───────────────────────────────────────────────────────────────────────
export function useRunMrp() {
  return useMutation({
    mutationFn: (demand: MrpDemandRow[]) => manufacturingApi.runMrp(demand),
  });
}

// ── standard costing ──────────────────────────────────────────────────────────
export function useStandardCost(params: {
  product_item_id: string;
  quantity: string;
  labor_minutes?: string;
  labor_rate_per_hour?: string;
  overhead_percent?: string;
} | null) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "costing", ws, params],
    queryFn: () => manufacturingApi.standardCost(params as NonNullable<typeof params>),
    enabled: enabled && !!params && !!params.product_item_id && !!params.quantity,
  });
}

// ── lots + quality ────────────────────────────────────────────────────────────
export function useLotTrace(lotId: string | undefined, enabled = true) {
  const { ws, enabled: scopeEnabled } = useScope();
  return useQuery({
    queryKey: ["manufacturing", "lots", ws, "trace", lotId],
    queryFn: () => manufacturingApi.traceLot(lotId as string),
    enabled: scopeEnabled && enabled && !!lotId,
  });
}
export function useCreateQualityCheck() {
  return useMutation({
    mutationFn: (data: {
      production_order_id: string;
      name: string;
      sampled_qty: string;
      passed_qty: string;
      failed_qty: string;
    }) => manufacturingApi.createQualityCheck(data),
  });
}
export function useCreateNcr() {
  return useMutation({
    mutationFn: (data: { production_order_id: string; defect: string }) =>
      manufacturingApi.createNcr(data),
  });
}
