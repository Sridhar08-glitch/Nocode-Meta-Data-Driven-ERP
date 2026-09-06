/**
 * App-wide reactive outbox singleton (Phase F3.8 integration). Wraps the pure {@link Outbox} with a
 * subscribe/notify store so React can render pending/conflict state via `useSyncExternalStore`, and a
 * default sender that replays queued mutations through the member API client (409 → conflict).
 */
import { apiSend } from "@/lib/api/request";
import { ApiError } from "@/lib/api/errors";

import { localStorageStore, memoryStore, Outbox, type OutboxItem, type OutboxStore, type Sender, type SendResult } from "./outbox";

class ReactiveStore implements OutboxStore {
  private cache: OutboxItem[];
  private listeners = new Set<() => void>();

  constructor(private backing: OutboxStore) {
    this.cache = backing.read();
  }
  read(): OutboxItem[] {
    return this.cache; // stable ref between writes (required by useSyncExternalStore)
  }
  write(items: OutboxItem[]): void {
    this.cache = items;
    this.backing.write(items);
    this.listeners.forEach((l) => l());
  }
  subscribe(l: () => void): () => void {
    this.listeners.add(l);
    return () => this.listeners.delete(l);
  }
}

const reactive = new ReactiveStore(typeof window === "undefined" ? memoryStore() : localStorageStore());

function genId(): string {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  } catch {
    /* fall through */
  }
  return `ob-${reactive.read().length}-${Date.now()}`;
}

export const outbox = new Outbox(reactive, genId);
export const subscribeOutbox = (l: () => void) => reactive.subscribe(l);
export const outboxSnapshot = (): OutboxItem[] => reactive.read();

/** Replay a queued mutation through the member API client. 409 ⇒ conflict (last-write-wins UI). */
export const defaultSender: Sender = async (item): Promise<SendResult> => {
  try {
    await apiSend(item.path, item.method, item.body);
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) {
      if (err.status === 409) return { ok: false, conflict: true, error: err.message };
      return { ok: false, error: err.message };
    }
    return { ok: false, error: "Network unavailable" };
  }
};

export const drainOutbox = () => outbox.drain(defaultSender);
