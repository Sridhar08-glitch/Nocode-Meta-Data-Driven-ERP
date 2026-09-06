"use client";

import { useQuery } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { useTenant } from "@/lib/tenant/context";

import { isRtlLocale, localizationApi, type WorkspaceLocale } from "./api";

interface I18nValue {
  locale: string;
  setLocale: (locale: string) => void;
  availableLocales: string[];
  dir: "ltr" | "rtl";
  /** Translate a dotted key; returns `fallback` (or the key) when missing. */
  t: (key: string, fallback?: string) => string;
  formatNumber: (n: number) => string;
  formatCurrency: (n: number) => string;
  formatDate: (d: string | number | Date) => string;
  workspaceLocale: WorkspaceLocale | undefined;
}

/**
 * Passthrough default: `t` returns the English fallback, formatters use the runtime locale. Used
 * when no provider is mounted (isolated component tests / SSR) so consumers never crash — the real
 * I18nProvider is always present in the app shell.
 */
const DEFAULT_I18N: I18nValue = {
  locale: "en-US",
  setLocale: () => {},
  availableLocales: ["en-US"],
  dir: "ltr",
  t: (_key, fallback) => fallback ?? _key,
  formatNumber: (n) => new Intl.NumberFormat("en-US").format(n),
  formatCurrency: (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n),
  formatDate: (d) => new Intl.DateTimeFormat("en-US").format(new Date(d)),
  workspaceLocale: undefined,
};

const I18nContext = createContext<I18nValue>(DEFAULT_I18N);
const STORAGE_KEY = "nexus.locale";

/** Provides the active locale, translations, direction, and locale-aware formatters. */
export function I18nProvider({ children }: { children: React.ReactNode }) {
  const { workspace, isReady } = useTenant();
  const ws = workspace?.slug ?? null;
  const enabled = isReady && !!ws;

  const localeQuery = useQuery({
    queryKey: ["i18n", ws, "locale"],
    queryFn: () => localizationApi.getLocale(),
    enabled,
    staleTime: 5 * 60_000,
  });

  const def = localeQuery.data?.default_locale ?? "en-US";
  const [override, setOverride] = useState<string | null>(null);

  // hydrate the per-user choice from localStorage once
  useEffect(() => {
    if (typeof window !== "undefined") setOverride(window.localStorage.getItem(STORAGE_KEY));
  }, []);

  const locale = override ?? def;

  const translationsQuery = useQuery({
    queryKey: ["i18n", ws, "translations", locale],
    queryFn: () => localizationApi.translations(locale),
    enabled: enabled && !!locale,
    staleTime: 5 * 60_000,
  });

  const dir = isRtlLocale(locale) ? "rtl" : "ltr";

  // reflect locale + direction on <html>
  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.lang = locale;
    document.documentElement.dir = dir;
  }, [locale, dir]);

  const setLocale = useCallback((next: string) => {
    setOverride(next);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const value = useMemo<I18nValue>(() => {
    const map = translationsQuery.data?.translations ?? {};
    const currency = localeQuery.data?.default_currency ?? "USD";
    return {
      locale,
      setLocale,
      availableLocales: localeQuery.data?.enabled_locales?.length ? localeQuery.data.enabled_locales : [def],
      dir,
      t: (key, fallback) => map[key] ?? fallback ?? key,
      formatNumber: (n) => new Intl.NumberFormat(locale).format(n),
      formatCurrency: (n) => new Intl.NumberFormat(locale, { style: "currency", currency }).format(n),
      formatDate: (d) => new Intl.DateTimeFormat(locale).format(new Date(d)),
      workspaceLocale: localeQuery.data,
    };
  }, [translationsQuery.data, localeQuery.data, locale, def, dir, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext);
}
