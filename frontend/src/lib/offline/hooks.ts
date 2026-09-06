"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import type { OutboxItem } from "./outbox";
import { drainOutbox, outboxSnapshot, subscribeOutbox } from "./store";

/** Reactive online/offline status from the browser. */
export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(typeof navigator === "undefined" ? true : navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}

const EMPTY: OutboxItem[] = [];

/** The live outbox contents (re-renders on enqueue/drain/resolve). */
export function useOutboxItems(): OutboxItem[] {
  return useSyncExternalStore(subscribeOutbox, outboxSnapshot, () => EMPTY);
}

/** Auto-drain the outbox whenever connectivity returns (and once on mount if already online). */
export function useOutboxAutoSync(): void {
  const online = useOnlineStatus();
  useEffect(() => {
    if (online) void drainOutbox();
  }, [online]);
}
