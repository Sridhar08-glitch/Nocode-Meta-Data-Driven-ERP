/**
 * Offline outbox (Phase F3.8) — a durable, ordered queue of mutations made while offline, replayed
 * on reconnect. Pure + storage-injectable (default localStorage) so the replay logic is unit-tested
 * without a service worker. Ordered replay (stop on first non-success to preserve order), bounded
 * retries (max 5 attempts → `failed`), and conflict surfacing for a last-write-wins resolution UI.
 *
 * The service-worker / Workbox precache + Web Push wiring is a separate build-pipeline concern (see
 * PHASE_F3_8_REPORT.md); this module is the queue + replay core the UI drives on `online` events.
 */
export type OutboxStatus = "pending" | "failed" | "conflict";

export interface OutboxItem {
  id: string;
  method: string;
  path: string;
  body?: unknown;
  /** label for the pending-changes UI, e.g. "Create lead" */
  label: string;
  status: OutboxStatus;
  attempts: number;
  createdAt: number;
  error?: string;
}

export interface OutboxStore {
  read(): OutboxItem[];
  write(items: OutboxItem[]): void;
}

export type SendResult = { ok: true } | { ok: false; conflict?: boolean; error?: string };
export type Sender = (item: OutboxItem) => Promise<SendResult>;

export const MAX_ATTEMPTS = 5;

export function localStorageStore(key = "nexus.outbox"): OutboxStore {
  return {
    read() {
      if (typeof window === "undefined") return [];
      try {
        return JSON.parse(window.localStorage.getItem(key) ?? "[]") as OutboxItem[];
      } catch {
        return [];
      }
    },
    write(items) {
      if (typeof window === "undefined") return;
      try {
        window.localStorage.setItem(key, JSON.stringify(items));
      } catch {
        /* storage full / unavailable */
      }
    },
  };
}

/** In-memory store (tests + SSR-safe default). */
export function memoryStore(initial: OutboxItem[] = []): OutboxStore {
  let items = [...initial];
  return {
    read: () => items,
    write: (next) => {
      items = next;
    },
  };
}

export class Outbox {
  constructor(
    private store: OutboxStore,
    private genId: () => string,
  ) {}

  list(): OutboxItem[] {
    return this.store.read();
  }
  pendingCount(): number {
    return this.list().filter((i) => i.status === "pending").length;
  }
  conflicts(): OutboxItem[] {
    return this.list().filter((i) => i.status === "conflict");
  }

  enqueue(input: { method: string; path: string; body?: unknown; label: string }, now: number): OutboxItem {
    const item: OutboxItem = {
      id: this.genId(),
      method: input.method,
      path: input.path,
      body: input.body,
      label: input.label,
      status: "pending",
      attempts: 0,
      createdAt: now,
    };
    this.store.write([...this.list(), item]);
    return item;
  }

  remove(id: string): void {
    this.store.write(this.list().filter((i) => i.id !== id));
  }

  private patch(id: string, p: Partial<OutboxItem>): void {
    this.store.write(this.list().map((i) => (i.id === id ? { ...i, ...p } : i)));
  }

  /** Last-write-wins resolution: keep "local" → re-queue to overwrite; keep "remote" → drop local. */
  resolveConflict(id: string, keep: "local" | "remote"): void {
    if (keep === "remote") {
      this.remove(id);
      return;
    }
    this.patch(id, { status: "pending", attempts: 0, error: undefined });
  }

  /** Manually retry a failed item. */
  retry(id: string): void {
    this.patch(id, { status: "pending", attempts: 0, error: undefined });
  }

  /**
   * Replay pending items in order. Stops at the first non-success so later mutations never jump
   * ahead of an unsynced earlier one. Returns a summary.
   */
  async drain(send: Sender): Promise<{ synced: number; conflicts: number; failed: number }> {
    let synced = 0;
    let conflicts = 0;
    let failed = 0;

    for (const item of this.list()) {
      if (item.status !== "pending") continue;
      const res = await send(item);
      if (res.ok) {
        this.remove(item.id);
        synced++;
        continue;
      }
      if (res.conflict) {
        this.patch(item.id, { status: "conflict", error: res.error });
        conflicts++;
        break; // preserve order — don't replay later items past a conflict
      }
      const attempts = item.attempts + 1;
      if (attempts >= MAX_ATTEMPTS) {
        this.patch(item.id, { status: "failed", attempts, error: res.error });
        failed++;
      } else {
        this.patch(item.id, { attempts, error: res.error });
      }
      break; // preserve order — stop on first failure, retry on next drain
    }
    return { synced, conflicts, failed };
  }
}
