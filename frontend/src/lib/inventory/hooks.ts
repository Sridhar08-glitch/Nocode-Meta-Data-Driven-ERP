"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { type Item, type ItemCategory, type Warehouse, inventoryApi } from "./api";

function useScope() {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const qc = useQueryClient();
  return {
    ws,
    enabled: isReady && !!ws,
    invalidate: () => qc.invalidateQueries({ queryKey: ["inventory", ws] }),
  };
}

// ── master data ────────────────────────────────────────────────────────────────
export function useItems() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["inventory", ws, "items"],
    queryFn: () => inventoryApi.listItems(),
    enabled,
    staleTime: 60_000,
  });
}
export function useCreateItem() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: Partial<Item>) => inventoryApi.createItem(data), onSuccess: invalidate });
}
export function useDeleteItem() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => inventoryApi.deleteItem(id), onSuccess: invalidate });
}

export function useWarehouses() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["inventory", ws, "warehouses"],
    queryFn: () => inventoryApi.listWarehouses(),
    enabled,
    staleTime: 60_000,
  });
}
export function useCreateWarehouse() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: Partial<Warehouse>) => inventoryApi.createWarehouse(data), onSuccess: invalidate });
}
export function useDeleteWarehouse() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (id: string) => inventoryApi.deleteWarehouse(id), onSuccess: invalidate });
}

export function useCategories() {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["inventory", ws, "categories"],
    queryFn: () => inventoryApi.listCategories(),
    enabled,
    staleTime: 60_000,
  });
}

// ── transactions ─────────────────────────────────────────────────────────────
export function useReceive() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: Record<string, unknown>) => inventoryApi.receive(data), onSuccess: invalidate });
}
export function useIssue() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: Record<string, unknown>) => inventoryApi.issue(data), onSuccess: invalidate });
}
export function useAdjust() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: Record<string, unknown>) => inventoryApi.adjust(data), onSuccess: invalidate });
}
export function useTransfer() {
  const { invalidate } = useScope();
  return useMutation({ mutationFn: (data: Record<string, unknown>) => inventoryApi.transfer(data), onSuccess: invalidate });
}

// ── reports ─────────────────────────────────────────────────────────────────
export function useStock(params?: { warehouse?: string; item?: string }) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["inventory", ws, "stock", params ?? {}],
    queryFn: () => inventoryApi.stock(params),
    enabled,
    staleTime: 15_000,
  });
}
export function useValuation(warehouse?: string) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["inventory", ws, "valuation", warehouse ?? null],
    queryFn: () => inventoryApi.valuation(warehouse),
    enabled,
    staleTime: 15_000,
  });
}
export function useMovements(params?: { item?: string; warehouse?: string }) {
  const { ws, enabled } = useScope();
  return useQuery({
    queryKey: ["inventory", ws, "movements", params ?? {}],
    queryFn: () => inventoryApi.movements(params),
    enabled,
    staleTime: 15_000,
  });
}

export type { ItemCategory };
