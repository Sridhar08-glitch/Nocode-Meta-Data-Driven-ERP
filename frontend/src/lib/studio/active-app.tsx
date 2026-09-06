"use client";

import { createContext, useContext, useEffect, useState } from "react";

/**
 * Active-application context (Phase F2.8). Kept SEPARATE from TenantContext so the workspace shell
 * is untouched: it just remembers which published Application is "active" so the sidebar/home can
 * scope to it. Persisted in localStorage; defaults to no-op when no provider is mounted (test-safe).
 */
interface ActiveAppValue {
  activeAppId: string | null;
  setActiveApp: (id: string | null) => void;
}

const ActiveAppContext = createContext<ActiveAppValue>({ activeAppId: null, setActiveApp: () => {} });
const KEY = "nexus.activeApp";

export function ActiveAppProvider({ children }: { children: React.ReactNode }) {
  const [activeAppId, setActiveAppId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") setActiveAppId(window.localStorage.getItem(KEY));
  }, []);

  function setActiveApp(id: string | null) {
    setActiveAppId(id);
    if (typeof window === "undefined") return;
    if (id) window.localStorage.setItem(KEY, id);
    else window.localStorage.removeItem(KEY);
  }

  return <ActiveAppContext.Provider value={{ activeAppId, setActiveApp }}>{children}</ActiveAppContext.Provider>;
}

export function useActiveApp(): ActiveAppValue {
  return useContext(ActiveAppContext);
}
