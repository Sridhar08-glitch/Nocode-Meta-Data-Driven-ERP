import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Readiness } from "@/lib/ops/api";

const readinessQ: { isLoading: boolean; isError: boolean; data: Readiness | undefined } = {
  isLoading: false,
  isError: false,
  data: undefined,
};
vi.mock("@/lib/ops/hooks", () => ({ useReadiness: () => readinessQ }));

import { SystemStatus } from "./system-status";

beforeEach(() => {
  readinessQ.isLoading = false;
  readinessQ.isError = false;
  readinessQ.data = undefined;
});

const ready: Readiness = {
  status: "ready",
  checks: {
    database: { ok: true, detail: "ok", latency_ms: 1.2 },
    cache: { ok: true, detail: "ok", latency_ms: 0.4 },
    broker: { ok: true, detail: "ok", latency_ms: 2.1 },
  },
};

describe("SystemStatus", () => {
  it("shows operational with per-component latency when ready", () => {
    readinessQ.data = ready;
    render(<SystemStatus />);
    expect(screen.getByText("All systems operational")).toBeInTheDocument();
    expect(screen.getByLabelText("database up")).toBeInTheDocument();
    expect(screen.getByText("1.2 ms")).toBeInTheDocument();
  });

  it("shows degraded and the failure detail when a component is down", () => {
    readinessQ.data = {
      status: "not_ready",
      checks: {
        database: { ok: true, detail: "ok", latency_ms: 1 },
        cache: { ok: false, detail: "ConnectionError: redis down", latency_ms: 2000 },
        broker: { ok: true, detail: "ok", latency_ms: 1 },
      },
    };
    render(<SystemStatus />);
    expect(screen.getByText("Degraded")).toBeInTheDocument();
    expect(screen.getByLabelText("cache down")).toBeInTheDocument();
    expect(screen.getByText("ConnectionError: redis down")).toBeInTheDocument();
  });

  it("renders an error state if the probe is unreachable", () => {
    readinessQ.isError = true;
    render(<SystemStatus />);
    expect(screen.getByText("Couldn't reach the readiness probe")).toBeInTheDocument();
  });
});
