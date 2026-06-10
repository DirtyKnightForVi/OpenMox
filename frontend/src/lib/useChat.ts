"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/stores/app";
import type { ChatMessage } from "@/lib/types";

const WS_URL = "ws://localhost:8000/ws";
const MAX_RECONNECT_DELAY_MS = 30_000;
const INITIAL_RECONNECT_DELAY_MS = 1_000;

export function useChat() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const store = useAppStore();
  const { currentWindowId, currentProject, addMessage, appendToLastMessage, setStreaming } = store;

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    clearReconnectTimer();
    const delay = Math.min(
      INITIAL_RECONNECT_DELAY_MS * 2 ** reconnectAttemptRef.current,
      MAX_RECONNECT_DELAY_MS,
    );
    reconnectAttemptRef.current += 1;
    console.log(`[WS] reconnecting in ${delay}ms (attempt ${reconnectAttemptRef.current})`);
    reconnectTimerRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [clearReconnectTimer]);

  const handleMessage = useCallback(
    (data: any) => {
      const type = data.type;
      const agentId = data._agent_id;

      if (type === "config:reloaded" || type === "server_info" || type === "session-status") return;
      if (type === "system_message") {
        addMessage({
          id: `sys-${Date.now()}`,
          sender: "system",
          text: data.content || "",
          timestamp: Date.now(),
          events: [],
        });
        return;
      }

      if (type === "HINT_BLOCK") {
        addMessage({
          id: `hint-${Date.now()}`,
          sender: agentId || "system",
          text: `[上下文] ${data._hint || ""}`,
          timestamp: data._timestamp * 1000,
          events: [],
        });
        return;
      }

      if (type === "REPLY_START") {
        setStreaming(true);
        addMessage({
          id: `reply-${data.reply_id}`,
          sender: agentId || "assistant",
          text: "",
          timestamp: data._timestamp * 1000,
          events: [],
        });
        return;
      }

      if (type === "TEXT_BLOCK_DELTA" && data.delta) {
        appendToLastMessage(agentId || "assistant", data.delta);
        return;
      }

      if (type === "REPLY_END") {
        setStreaming(false);
        return;
      }

      if (type === "TOOL_CALL_END") {
        const toolName = data.name || "tool";
        appendToLastMessage(agentId || "assistant", ` [🔧 ${toolName}] `);
        return;
      }

      if (type === "TOOL_RESULT_END") {
        const state = data.state;
        if (state === "success") {
          appendToLastMessage(agentId || "assistant", " ✅");
        } else if (state === "error" || state === "denied") {
          appendToLastMessage(agentId || "assistant", " ❌");
        }
        return;
      }
    },
    [addMessage, appendToLastMessage, setStreaming],
  );

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) return;
    intentionalCloseRef.current = false;
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] connected");
      reconnectAttemptRef.current = 0; // Reset backoff on successful connect
    };

    ws.onmessage = (event) => {
      try {
        handleMessage(JSON.parse(event.data));
      } catch (e) {
        console.warn("[WS] parse error", e);
      }
    };

    ws.onclose = () => {
      console.log("[WS] disconnected");
      wsRef.current = null;
      if (!intentionalCloseRef.current) {
        scheduleReconnect();
      }
    };

    ws.onerror = (e) => {
      console.error("[WS] error", e);
    };
  }, [handleMessage, scheduleReconnect]);

  const sendMessage = useCallback(
    (command: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.warn("[WS] not connected, can't send");
        return;
      }
      if (!currentWindowId) return;
      const cwd = currentProject?.full_path || ".";

      addMessage({
        id: `user-${Date.now()}`,
        sender: "user",
        text: command,
        timestamp: Date.now(),
        events: [],
      });

      wsRef.current.send(
        JSON.stringify({
          type: "pilotdeck-command",
          command,
          options: {
            sessionKey: currentWindowId,
            sessionId: currentWindowId,
            projectPath: cwd,
            cwd,
          },
        }),
      );
    },
    [currentWindowId, currentProject, addMessage],
  );

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    clearReconnectTimer();
    wsRef.current?.close();
    wsRef.current = null;
  }, [clearReconnectTimer]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      clearReconnectTimer();
      wsRef.current?.close();
    };
  }, [clearReconnectTimer]);

  return { connect, sendMessage, disconnect };
}
