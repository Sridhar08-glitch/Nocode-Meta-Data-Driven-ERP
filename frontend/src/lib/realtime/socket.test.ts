import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildSocketUrl, createReconnectingSocket, type SocketStatus } from "./socket";

class MockWS {
  static instances: MockWS[] = [];
  url: string;
  closed = false;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(url: string) {
    this.url = url;
    MockWS.instances.push(this);
  }
  close() {
    this.closed = true;
  }
}

let timers: { cb: () => void; delay: number }[] = [];
const setT = ((cb: () => void, delay: number) => {
  timers.push({ cb, delay });
  return timers.length as unknown as ReturnType<typeof setTimeout>;
}) as typeof setTimeout;
const clearT = (() => undefined) as typeof clearTimeout;
function flushTimer() {
  const t = timers.shift();
  t?.cb();
  return t?.delay;
}

let hidden = false;
let visCb: () => void = () => undefined;
const visibility = {
  isHidden: () => hidden,
  subscribe: (cb: () => void) => {
    visCb = cb;
    return () => undefined;
  },
};

function open(onMessage = vi.fn(), onStatus?: (s: SocketStatus) => void) {
  return createReconnectingSocket({
    path: "ws/notifications/",
    onMessage,
    onStatus,
    getToken: () => "tok123",
    baseUrl: "http://localhost:8000",
    WebSocketImpl: MockWS as unknown as typeof WebSocket,
    setTimeoutImpl: setT,
    clearTimeoutImpl: clearT,
    visibility,
  });
}

beforeEach(() => {
  MockWS.instances = [];
  timers = [];
  hidden = false;
  visCb = () => undefined;
});

describe("buildSocketUrl", () => {
  it("converts http→ws and appends the token", () => {
    expect(buildSocketUrl("http://localhost:8000", "ws/notifications/", "abc")).toBe(
      "ws://localhost:8000/ws/notifications/?token=abc",
    );
    expect(buildSocketUrl("https://api.example.com/", "/ws/x/", null)).toBe(
      "wss://api.example.com/ws/x/",
    );
  });
});

describe("createReconnectingSocket", () => {
  it("connects with the token and reports open", () => {
    const onStatus = vi.fn();
    open(vi.fn(), onStatus);
    expect(MockWS.instances).toHaveLength(1);
    expect(MockWS.instances[0].url).toBe("ws://localhost:8000/ws/notifications/?token=tok123");
    expect(onStatus).toHaveBeenCalledWith("connecting");
    MockWS.instances[0].onopen!();
    expect(onStatus).toHaveBeenCalledWith("open");
  });

  it("parses JSON messages and ignores malformed frames", () => {
    const onMessage = vi.fn();
    open(onMessage);
    MockWS.instances[0].onmessage!({ data: JSON.stringify({ type: "notification.created", id: "n1" }) });
    expect(onMessage).toHaveBeenCalledWith({ type: "notification.created", id: "n1" });
    MockWS.instances[0].onmessage!({ data: "not json" });
    expect(onMessage).toHaveBeenCalledTimes(1);
  });

  it("reconnects with exponential backoff after a close", () => {
    open();
    MockWS.instances[0].onopen!();
    MockWS.instances[0].onclose!();
    expect(flushTimer()).toBe(1000); // first backoff
    expect(MockWS.instances).toHaveLength(2);
    MockWS.instances[1].onclose!();
    expect(flushTimer()).toBe(2000); // doubled
    expect(MockWS.instances).toHaveLength(3);
  });

  it("resets backoff after a successful open", () => {
    open();
    MockWS.instances[0].onclose!();
    flushTimer(); // 1000 → instance[1]
    MockWS.instances[1].onopen!(); // success resets attempts
    MockWS.instances[1].onclose!();
    expect(flushTimer()).toBe(1000); // back to base
  });

  it("pauses while the tab is hidden and resumes when visible", () => {
    open();
    hidden = true;
    visCb();
    expect(MockWS.instances[0].closed).toBe(true);
    expect(timers).toHaveLength(0); // no reconnect scheduled while hidden
    hidden = false;
    visCb();
    expect(MockWS.instances).toHaveLength(2); // reconnected immediately
  });

  it("does not reconnect after close()", () => {
    const handle = open();
    handle.close();
    expect(MockWS.instances[0].closed).toBe(true);
    MockWS.instances[0].onclose?.(); // late close event
    expect(timers).toHaveLength(0);
    expect(MockWS.instances).toHaveLength(1);
  });

  it("closes the socket on error", () => {
    open();
    MockWS.instances[0].onerror!();
    expect(MockWS.instances[0].closed).toBe(true);
  });
});
