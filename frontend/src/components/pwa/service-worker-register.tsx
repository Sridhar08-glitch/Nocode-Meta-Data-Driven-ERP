"use client";

import { useEffect } from "react";

/**
 * Registers the PWA service worker (Phase F3.8) — production only, so dev/test/HMR are untouched.
 * Failures are swallowed (the app works fine without it). Renders nothing.
 */
export function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* installability is best-effort */
    });
  }, []);
  return null;
}
