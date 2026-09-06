"use client";

import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import {
  applyBranding,
  applyPersonalization,
  type EffectiveAppearance,
  resetBranding,
  resetPersonalization,
  type WorkspaceBranding,
} from "@/lib/branding/apply";
import { metadataApi } from "@/lib/metadata/api";
import { personalizationApi } from "@/lib/personalization/api";

import { useTenantStore } from "./store";
import type { FeatureFlags, Workspace } from "./types";

const ACTIVE_KEY = "nexus.ws";

interface TenantContextValue {
  workspace: Workspace | null;
  workspaces: Workspace[];
  flags: FeatureFlags;
  branding: WorkspaceBranding | null;
  appearance: EffectiveAppearance | null;
  isReady: boolean;
  isLoading: boolean;
  switchWorkspace: (slug: string) => void;
  hasFlag: (key: string) => boolean;
}

const TenantContext = createContext<TenantContextValue | null>(null);

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const storeSlug = useTenantStore((s) => s.workspaceSlug);
  const setWorkspaceSlug = useTenantStore((s) => s.setWorkspaceSlug);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);

  const workspacesQuery = useQuery({
    queryKey: ["workspaces"],
    queryFn: metadataApi.workspaces,
    staleTime: 5 * 60_000,
  });
  const workspaces = useMemo(() => workspacesQuery.data ?? [], [workspacesQuery.data]);

  // Resolve the active workspace once the list loads (persisted choice → else first).
  useEffect(() => {
    if (!workspaces.length) return;
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(ACTIVE_KEY) : null;
    const chosen = workspaces.find((w) => w.slug === stored) ?? workspaces[0];
    setActiveSlug((cur) => cur ?? chosen.slug);
  }, [workspaces]);

  // Sync the active slug into the store (the API client injects X-Workspace-Slug from it).
  useEffect(() => {
    if (!activeSlug) return;
    setWorkspaceSlug(activeSlug);
    if (typeof window !== "undefined") window.localStorage.setItem(ACTIVE_KEY, activeSlug);
  }, [activeSlug, setWorkspaceSlug]);

  // Tenant-scoped queries fire only once the store header matches (correct slug on the wire).
  const ready = !!activeSlug && storeSlug === activeSlug;

  const brandingQuery = useQuery({
    queryKey: ["branding", activeSlug],
    queryFn: metadataApi.branding,
    enabled: ready,
    staleTime: 5 * 60_000,
  });
  const flagsQuery = useQuery({
    queryKey: ["flags", activeSlug],
    queryFn: metadataApi.activeFlags,
    enabled: ready,
    staleTime: 5 * 60_000,
  });
  // Per-user appearance overlay (resolved server-side over workspace branding → role → user).
  const appearanceQuery = useQuery({
    queryKey: ["appearance", activeSlug],
    queryFn: personalizationApi.appearance,
    enabled: ready,
    staleTime: 5 * 60_000,
  });
  const appearance = appearanceQuery.data?.appearance ?? null;

  // Re-theme on branding change, THEN overlay the user's personalization so user overrides win over
  // workspace defaults (locked keys were already resolved out server-side). Restore both on unmount.
  useEffect(() => {
    applyBranding(brandingQuery.data);
    applyPersonalization(appearance);
    return () => {
      resetPersonalization();
      resetBranding();
    };
  }, [brandingQuery.data, appearance]);

  const value = useMemo<TenantContextValue>(() => {
    const flags = flagsQuery.data?.flags ?? {};
    return {
      workspace: workspaces.find((w) => w.slug === activeSlug) ?? null,
      workspaces,
      flags,
      branding: brandingQuery.data ?? null,
      appearance,
      isReady: ready,
      isLoading: workspacesQuery.isLoading,
      switchWorkspace: (slug) => setActiveSlug(slug),
      hasFlag: (key) => flags[key]?.enabled ?? false,
    };
  }, [workspaces, activeSlug, ready, flagsQuery.data, brandingQuery.data, appearance, workspacesQuery.isLoading]);

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}

export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext);
  if (!ctx) throw new Error("useTenant must be used within a TenantProvider");
  return ctx;
}
