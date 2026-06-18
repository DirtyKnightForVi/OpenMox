"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/stores/app";
import type { ChatMessage } from "@/lib/types";

const WS_URL = "ws://localhost:8000/ws";
const MAX_RECONNECT_DELAY_MS = 30_000;
const INITIAL_RECONNECT_DELAY_MS = 1_000;

/**
 * WebSocket chat hook.
 * Full support for the OpenMox WebSocket protocol (PlanC/07).
 */
export function useChat() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const store = useAppStore();
  const {
    currentWindowId,
    currentProject,
    currentProjectPath,
    addMessage,
    appendToLastMessage,
    appendThinkingToLastMessage,
    setStreaming,
    setAgentStatus,
    updateWorkDetail,
    addToolCallToAgent,
    setWsConnected,
  } = store;

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

      // ── Handshake messages (ignore) ──
      if (type === "config:reloaded" || type === "server_info") return;

      // ── Session status (heartbeat) ──
      if (type === "session-status") return;

      // ── Agent status events ──
      if (type === "agent:busy") {
        setAgentStatus(agentId || "unknown", "busy");
        if (agentId) {
          updateWorkDetail(agentId, {
            currentTask: data._source || "Working...",
          });
        }
        return;
      }

      if (type === "agent:idle") {
        setAgentStatus(agentId || "unknown", "idle");
        // Reset work detail — agent has finished its current task
        if (agentId) {
          updateWorkDetail(agentId, { currentTask: undefined });
        }
        return;
      }

      // ── Human message echo ──
      if (type === "human_message") {
        addMessage({
          id: `user-${data._timestamp || Date.now()}`,
          sender: "user",
          text: data.content || "",
          timestamp: (data._timestamp || 0) * 1000,
          events: [],
        });
        return;
      }

      // ── System message ──
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

      // ── HINT_BLOCK (context seeding) ──
      // These are internal context-seeding events from
      // ContextSeedingMiddleware — they exist to seed agent
      // memory, not for human display.  Silently consume them.
      if (type === "HINT_BLOCK") return;

      // ── REPLY_START ──
      if (type === "REPLY_START") {
        setStreaming(true);
        addMessage({
          id: `reply-${data.reply_id}`,
          sender: agentId || "assistant",
          text: "",
          timestamp: (data._timestamp || 0) * 1000,
          events: [],
        });
        return;
      }

      // ── TEXT_BLOCK_DELTA (incremental text) ──
      if (type === "TEXT_BLOCK_DELTA" && data.delta) {
        appendToLastMessage(agentId || "assistant", data.delta);
        return;
      }

      // ── THINKING_BLOCK_DELTA (reasoning, rendered as gray collapsible) ──
      if (type === "THINKING_BLOCK_DELTA" && data.delta) {
        appendThinkingToLastMessage(agentId || "assistant", data.delta);
        return;
      }

      // ── TEXT_BLOCK_END / THINKING_BLOCK_END (no-op, transition markers) ──
      if (type === "TEXT_BLOCK_END" || type === "THINKING_BLOCK_END") return;

      // ── REPLY_END ──
      if (type === "REPLY_END") {
        setStreaming(false);
        return;
      }

      // ── TOOL events ──
      if (type === "TOOL_CALL_END") {
        const toolName = data.name || "tool";
        appendToLastMessage(agentId || "assistant", ` [🔧 ${toolName}] `);
        // Populate agent work detail so AgentPanel can show active tool calls
        if (agentId) {
          addToolCallToAgent(agentId, {
            name: toolName,
            _source: data._source,
            _timestamp: data._timestamp || Date.now(),
          });
          updateWorkDetail(agentId, { currentTask: `🔧 ${toolName}` });
        }
        return;
      }

      if (type === "TOOL_RESULT_END") {
        const state = data.state;
        if (state === "success") {
          appendToLastMessage(agentId || "assistant", " ✅");
        } else if (state === "error" || state === "denied") {
          appendToLastMessage(agentId || "assistant", " ❌");
        }
        // Update work detail with tool result state
        if (agentId) {
          addToolCallToAgent(agentId, {
            name: data.name || "tool",
            state,
            _source: data._source,
            _timestamp: data._timestamp || Date.now(),
          });
          const stateLabel = state === "success" ? "✅" : "❌";
          updateWorkDetail(agentId, { currentTask: `${stateLabel} ${data.name || "tool"}` });
        }
        return;
      }

      // ── EXCEED_MAX_ITERS ──
      if (type === "EXCEED_MAX_ITERS") {
        appendToLastMessage(agentId || "assistant", "\n\n⚠️ Agent 思考轮次过多，已中断。");
        setStreaming(false);
        return;
      }
    },
    [addMessage, appendToLastMessage, appendThinkingToLastMessage, setStreaming,
     setAgentStatus, updateWorkDetail, addToolCallToAgent, setWsConnected],
  );

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING)
      return;

    // Mute callbacks on the previous WebSocket so that its async events
    // (onclose / onerror) cannot interfere with the new connection.
    // This is essential in React StrictMode where the cleanup-effect
    // cycle closes one socket right before the next connect() call.
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
    }

    intentionalCloseRef.current = false;
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] connected");
      reconnectAttemptRef.current = 0;
      setWsConnected(true);
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
      setWsConnected(false);
      // Only clear ref if it still points to this WebSocket.
      // Prevents StrictMode double-mount races where a stale
      // onclose handler clears a newer connection's reference.
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
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
      // Resolve project path: prefer store value, fall back to
      // currentProject.full_path, then to "." as last resort.
      const cwd = currentProjectPath
        || currentProject?.full_path
        || ".";

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
    [currentWindowId, currentProject, currentProjectPath],
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
