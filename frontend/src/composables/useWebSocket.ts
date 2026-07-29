import { onBeforeUnmount, onMounted } from "vue";

import { wsUrl } from "../config";
import { useDashboardStore } from "../stores/dashboard";
import type { WsEvent } from "../types";

const MAX_BACKOFF_MS = 30_000;

/** Owns the dashboard WebSocket for the lifetime of the mounting component:
 * connects, feeds events into the store, reconnects with capped exponential
 * backoff, and closes cleanly on unmount. */
export function useDashboardSocket(): void {
  const store = useDashboardStore();
  let socket: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let backoffMs = 1_000;
  let closed = false;

  function connect(): void {
    store.setConnection("connecting");
    socket = new WebSocket(wsUrl("/ws/dashboard"));

    socket.onopen = () => {
      backoffMs = 1_000;
      store.setConnection("online");
    };

    socket.onmessage = (message: MessageEvent<string>) => {
      let event: WsEvent;
      try {
        event = JSON.parse(message.data) as WsEvent;
      } catch {
        return; // malformed frame; ignore rather than kill the stream
      }
      store.applyEvent(event);
    };

    socket.onclose = () => {
      if (closed) {
        return;
      }
      store.setConnection("offline");
      reconnectTimer = setTimeout(connect, backoffMs);
      backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
    };

    socket.onerror = () => {
      socket?.close();
    };
  }

  onMounted(connect);
  onBeforeUnmount(() => {
    closed = true;
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
    }
    socket?.close();
  });
}
