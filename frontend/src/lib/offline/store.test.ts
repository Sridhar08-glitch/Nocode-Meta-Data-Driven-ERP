import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";

const apiSend = vi.fn();
vi.mock("@/lib/api/request", () => ({ apiSend: (...a: unknown[]) => apiSend(...a) }));

import { defaultSender } from "./store";
import type { OutboxItem } from "./outbox";

const item: OutboxItem = { id: "i1", method: "PATCH", path: "/data/lead/1/", body: { x: 1 }, label: "Update", status: "pending", attempts: 0, createdAt: 0 };

beforeEach(() => apiSend.mockReset());
afterEach(() => vi.clearAllMocks());

describe("defaultSender", () => {
  it("replays the mutation through apiSend on success", async () => {
    apiSend.mockResolvedValueOnce({});
    expect(await defaultSender(item)).toEqual({ ok: true });
    expect(apiSend).toHaveBeenCalledWith("/data/lead/1/", "PATCH", { x: 1 });
  });

  it("maps a 409 to a conflict", async () => {
    apiSend.mockRejectedValueOnce(new ApiError({ status: 409, message: "stale" }));
    expect(await defaultSender(item)).toEqual({ ok: false, conflict: true, error: "stale" });
  });

  it("treats other errors as retryable failures", async () => {
    apiSend.mockRejectedValueOnce(new ApiError({ status: 500, message: "boom" }));
    expect(await defaultSender(item)).toEqual({ ok: false, error: "boom" });
    apiSend.mockRejectedValueOnce(new Error("network"));
    expect(await defaultSender(item)).toEqual({ ok: false, error: "Network unavailable" });
  });
});
