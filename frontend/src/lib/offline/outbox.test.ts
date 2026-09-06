import { describe, expect, it, vi } from "vitest";

import { MAX_ATTEMPTS, memoryStore, Outbox, type Sender } from "./outbox";

function makeOutbox() {
  let n = 0;
  return new Outbox(memoryStore(), () => `id${++n}`);
}

describe("Outbox", () => {
  it("enqueues pending items and counts them", () => {
    const ob = makeOutbox();
    ob.enqueue({ method: "POST", path: "/a", label: "Create A" }, 1000);
    ob.enqueue({ method: "POST", path: "/b", label: "Create B" }, 1001);
    expect(ob.pendingCount()).toBe(2);
    expect(ob.list()[0].label).toBe("Create A");
  });

  it("drains in order, removing each synced item", async () => {
    const ob = makeOutbox();
    ob.enqueue({ method: "POST", path: "/a", label: "A" }, 1);
    ob.enqueue({ method: "POST", path: "/b", label: "B" }, 2);
    const ok: Sender = async () => ({ ok: true });
    const r1 = await ob.drain(ok); // drains all consecutive successes in one pass
    expect(r1.synced).toBe(2);
    expect(ob.pendingCount()).toBe(0);
  });

  it("stops at the first failure to preserve order", async () => {
    const ob = makeOutbox();
    ob.enqueue({ method: "POST", path: "/a", label: "A" }, 1);
    ob.enqueue({ method: "POST", path: "/b", label: "B" }, 2);
    const send = vi.fn<Sender>(async () => ({ ok: false, error: "offline" }));
    await ob.drain(send);
    expect(send).toHaveBeenCalledTimes(1); // did not advance to B
    expect(ob.list()[0].attempts).toBe(1);
    expect(ob.list()[1].attempts).toBe(0);
  });

  it("marks an item failed after MAX_ATTEMPTS", async () => {
    const ob = makeOutbox();
    ob.enqueue({ method: "POST", path: "/a", label: "A" }, 1);
    const fail: Sender = async () => ({ ok: false, error: "boom" });
    for (let i = 0; i < MAX_ATTEMPTS; i++) await ob.drain(fail);
    expect(ob.list()[0].status).toBe("failed");
    expect(ob.pendingCount()).toBe(0);
    ob.retry(ob.list()[0].id);
    expect(ob.pendingCount()).toBe(1);
  });

  it("surfaces conflicts and resolves last-write-wins", async () => {
    const ob = makeOutbox();
    const item = ob.enqueue({ method: "PATCH", path: "/a", label: "Update A" }, 1);
    const conflict: Sender = async () => ({ ok: false, conflict: true, error: "stale" });
    const r = await ob.drain(conflict);
    expect(r.conflicts).toBe(1);
    expect(ob.conflicts()).toHaveLength(1);

    // keep remote → drop local
    ob.resolveConflict(item.id, "remote");
    expect(ob.list()).toHaveLength(0);

    // keep local → re-queue
    const item2 = ob.enqueue({ method: "PATCH", path: "/b", label: "Update B" }, 2);
    await ob.drain(conflict);
    ob.resolveConflict(item2.id, "local");
    expect(ob.pendingCount()).toBe(1);
  });
});
