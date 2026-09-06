/**
 * The ONE realtime client (Phase F1.10). A reconnecting WebSocket wrapper used by the
 * notification center (`ws/notifications/?token=`). Handles: JWT-in-query auth, exponential
 * backoff reconnect, pause-while-tab-hidden (close on hidden, reconnect on visible), and clean
 * teardown. Protocol-agnostic — the caller supplies `path` and an `onMessage(json)` handler.
 *
 * Dependencies (WebSocket ctor, visibility source, timers) are injectable so it is fully testable.
 */
import { API_BASE_URL } from "@/lib/api/config";
import { getAccessToken } from "@/lib/auth/token-store";

export type SocketStatus = "connecting" | "open" | "closed";

export interface ReconnectingSocketOptions {
  /** WS path, e.g. "ws/notifications/". Leading slash optional. */
  path: string;
  onMessage: (data: unknown) => void;
  onStatus?: (status: SocketStatus) => void;
  /** Token provider (defaults to the in-memory access token). */
  getToken?: () => string | null;
  /** Base http(s) URL; converted to ws(s). Defaults to the API base. */
  baseUrl?: string;
  /** Injectables for testing. */
  WebSocketImpl?: typeof WebSocket;
  setTimeoutImpl?: typeof setTimeout;
  clearTimeoutImpl?: typeof clearTimeout;
  /** Visibility source; defaults to document. */
  visibility?: { isHidden: () => boolean; subscribe: (cb: () => void) => () => void };
}

const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1_000;

/** Convert an http(s) base URL + path into a token-authenticated ws(s) URL. */
export function buildSocketUrl(baseUrl: string, path: string, token: string | null): string {
  const wsBase = baseUrl.replace(/^http/, "ws").replace(/\/$/, "");
  const cleanPath = path.replace(/^\//, "");
  const qs = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${wsBase}/${cleanPath}${qs}`;
}

function documentVisibility() {
  return {
    isHidden: () => typeof document !== "undefined" && document.visibilityState === "hidden",
    subscribe: (cb: () => void) => {
      if (typeof document === "undefined") return () => undefined;
      document.addEventListener("visibilitychange", cb);
      return () => document.removeEventListener("visibilitychange", cb);
    },
  };
}

export interface ReconnectingSocket {
  close: () => void;
}

/** Open a managed, reconnecting socket. Returns a handle with `close()`. */
export function createReconnectingSocket(opts: ReconnectingSocketOptions): ReconnectingSocket {
  const WS = opts.WebSocketImpl ?? WebSocket;
  const setT = opts.setTimeoutImpl ?? setTimeout;
  const clearT = opts.clearTimeoutImpl ?? clearTimeout;
  const baseUrl = opts.baseUrl ?? API_BASE_URL;
  const getToken = opts.getToken ?? getAccessToken;
  const vis = opts.visibility ?? documentVisibility();

  let ws: WebSocket | null = null;
  let attempts = 0;
  let retryTimer: ReturnType<typeof setTimeout> | null = null;
  let disposed = false;

  const setStatus = (s: SocketStatus) => opts.onStatus?.(s);

  function clearRetry() {
    if (retryTimer) {
      clearT(retryTimer);
      retryTimer = null;
    }
  }

  function scheduleReconnect() {
    if (disposed || vis.isHidden()) return;
    const delay = Math.min(BASE_BACKOFF_MS * 2 ** attempts, MAX_BACKOFF_MS);
    attempts += 1;
    retryTimer = setT(connect, delay);
  }

  function connect() {
    if (disposed || vis.isHidden()) return;
    clearRetry();
    setStatus("connecting");
    const socket = new WS(buildSocketUrl(baseUrl, opts.path, getToken()));
    ws = socket;

    socket.onopen = () => {
      attempts = 0;
      setStatus("open");
    };
    socket.onmessage = (event: MessageEvent) => {
      try {
        opts.onMessage(JSON.parse(event.data));
      } catch {
        /* ignore non-JSON frames */
      }
    };
    socket.onclose = () => {
      setStatus("closed");
      if (!disposed && !vis.isHidden()) scheduleReconnect();
    };
    socket.onerror = () => socket.close();
  }

  function teardownSocket() {
    if (ws) {
      ws.onclose = null;
      ws.onerror = null;
      ws.onmessage = null;
      ws.onopen = null;
      ws.close();
      ws = null;
    }
  }

  const unsubscribe = vis.subscribe(() => {
    if (vis.isHidden()) {
      clearRetry();
      teardownSocket();
      setStatus("closed");
    } else if (!disposed) {
      attempts = 0;
      connect();
    }
  });

  connect();

  return {
    close() {
      disposed = true;
      clearRetry();
      teardownSocket();
      unsubscribe();
    },
  };
}
