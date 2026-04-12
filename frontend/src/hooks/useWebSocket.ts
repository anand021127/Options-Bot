/**
 * useWebSocket hook
 * Connects to backend WS, auto-reconnects, dispatches events to state.
 */

import { useEffect, useRef, useCallback, useState } from 'react';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
const RECONNECT_DELAY = 3000;

type WsMessage = { event: string; data: any };
type Handler = (data: any) => void;

export function useWebSocket(handlers: Record<string, Handler>) {
  const wsRef       = useRef<WebSocket | null>(null);
  const timerRef    = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handlersRef = useRef(handlers);
  const [connected, setConnected] = useState(false);

  // Keep handlers ref up to date without re-creating socket
  handlersRef.current = handlers;

  const connect = useCallback(() => {
    if (typeof window === 'undefined') return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      // Heartbeat ping every 30s to keep connection alive
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30000);
      (ws as any)._pingInterval = ping;
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        const handler = handlersRef.current[msg.event];
        if (handler) handler(msg.data);
      } catch {}
    };

    ws.onclose = () => {
      setConnected(false);
      clearInterval((ws as any)._pingInterval);
      // Auto-reconnect
      timerRef.current = setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      timerRef.current && clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
