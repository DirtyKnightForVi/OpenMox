"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/stores/app";

const WS_URL = "ws://localhost:8000/ws";
const MAX_RECONNECT_DELAY_MS = 30_000;
const INITIAL_RECONNECT_DELAY_MS = 1_000;

/**
 * Hybrid chat hook: WebSocket (group chat + agent status) + SSE (agent internal events).
 *
 * WebSocket (/ws):
 *   - human_message / agent_report → group chat bubbles
 *   - agent:busy / agent:idle → agent status
 *   - task_progress → task panel
 *   - system_message → error / info toasts
 *
 * SSE (/api/sessions/{sid}/stream?agent_id={aid}):
 *   - AgentScope native events (THINKING, TOOL_CALL, TOOL_RESULT, TEXT)
 *   - Auto-started on agent:busy, auto-closed on agent:idle
 */
export function useChat() {
  const wsRef = useRef<WebSocket | null>(null);
  const sseRefs = useRef<Map<string, EventSource>>(new Map());
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const intentionalCloseRef = useRef(false);
  const store = useAppStore();
  const {
    currentWindowId,
    currentProject,
    currentProjectPath,
    addMessage,
    setAgentStatus,
    updateWorkDetail,
    addToolCallToAgent,
    addThinkingToAgent,
    setWsConnected,
    addTaskProgress,
  } = store;

  // ── SSE management ──────────────────────────────

  const startSse = useCallback(
    (agentId: string, sessionId: string) => {
      // Close existing SSE for this agent
      const existing = sseRefs.current.get(agentId);
      if (existing) {
        existing.close();
      }

      const projectPath = useAppStore.getState().currentProjectPath || ".";
      const url = `http://localhost:8000/api/sessions/${encodeURIComponent(sessionId)}/stream?agent_id=${encodeURIComponent(agentId)}&project_path=${encodeURIComponent(projectPath)}`;
      console.log(`[SSE] connecting ${agentId}: ${url}`);
      const es = new EventSource(url);
      sseRefs.current.set(agentId, es);

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleSseEvent(agentId, data);
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        console.log(`[SSE] ${agentId} connection error/closed`);
        es.close();
        sseRefs.current.delete(agentId);
      };
    },
    [addToolCallToAgent, addThinkingToAgent, updateWorkDetail, addTaskProgress],
  );

  const stopSse = useCallback((agentId: string) => {
    const es = sseRefs.current.get(agentId);
    if (es) {
      es.close();
      sseRefs.current.delete(agentId);
      console.log(`[SSE] ${agentId} closed`);
    }
  }, []);

  const closeAllSse = useCallback(() => {
    for (const [agentId, es] of sseRefs.current) {
      es.close();
    }
    sseRefs.current.clear();
  }, []);

  // ── SSE event handler ───────────────────────────

  const handleSseEvent = useCallback(
    (agentId: string, data: any) => {
      const etype = data.type || "?";

      // Task panel progress events (from TaskPanelProjector)
      if (etype === "task_progress" || data.name === "task_progress") {
        addTaskProgress({
          worker_session_id: data.worker_session_id || "",
          worker_agent_id: data.worker_agent_id || agentId,
          worker_agent_name: data.worker_agent_name || "",
          reply_id: data.reply_id || "",
          event_type: data.event_type || etype,
          event_seq: data.event_seq || 0,
          timestamp: (data.timestamp || data._timestamp || 0) * 1000,
          delta: data.delta,
          thinking_started: data.thinking_started,
          thinking_ended: data.thinking_ended,
          tool_name: data.tool_name || data.name,
          tool_input: data.tool_input,
          tool_state: data.tool_state || data.state,
          tool_output: data.tool_output || data.output,
          tool_result_started: data.tool_result_started,
          summary: data.summary || data.text,
        });
        return;
      }

      // THINKING → agent work detail + task progress
      if (etype === "THINKING_BLOCK_DELTA" && data.delta) {
        addThinkingToAgent(agentId, data.delta);
        addTaskProgress({
          worker_session_id: "",
          worker_agent_id: agentId,
          worker_agent_name: "",
          reply_id: "",
          event_type: etype,
          event_seq: 0,
          timestamp: Date.now(),
          delta: data.delta,
        });
        return;
      }

      if (etype === "THINKING_BLOCK_START") {
        addTaskProgress({
          worker_session_id: "", worker_agent_id: agentId,
          worker_agent_name: "", reply_id: "",
          event_type: etype, event_seq: 0, timestamp: Date.now(),
          thinking_started: true,
        });
        return;
      }

      if (etype === "THINKING_BLOCK_END") {
        addTaskProgress({
          worker_session_id: "", worker_agent_id: agentId,
          worker_agent_name: "", reply_id: "",
          event_type: etype, event_seq: 0, timestamp: Date.now(),
          thinking_ended: true,
        });
        return;
      }

      // TOOL_CALL_START → capture tool name
      if (etype === "TOOL_CALL_START") {
        const toolName = data.tool_call_name || "tool";
        addTaskProgress({
          worker_session_id: "", worker_agent_id: agentId,
          worker_agent_name: "", reply_id: "",
          event_type: etype, event_seq: 0, timestamp: Date.now(),
          tool_name: toolName,
        });
        return;
      }

      // TOOL_CALL_END — update agent status only (no name in this event)
      if (etype === "TOOL_CALL_END") {
        addToolCallToAgent(agentId, {
          name: "tool",
          _timestamp: data._timestamp || Date.now(),
        });
        updateWorkDetail(agentId, { currentTask: `🔧 tool` });
        return;
      }

      // TOOL_RESULT — result status only (name was in TOOL_CALL_START)
      if (etype === "TOOL_RESULT_END") {
        const state = data.state;
        addToolCallToAgent(agentId, {
          name: "tool",
          state: state,
          _timestamp: data._timestamp || Date.now(),
        });
        const stateLabel = state === "success" ? "✅" : "❌";
        updateWorkDetail(agentId, {
          currentTask: `${stateLabel} tool`,
        });
        addTaskProgress({
          worker_session_id: "", worker_agent_id: agentId,
          worker_agent_name: "", reply_id: "",
          event_type: etype, event_seq: 0, timestamp: Date.now(),
          tool_state: state,
          tool_output: data.output,
        });
        return;
      }

      // TEXT → task progress summary
      if (etype === "TEXT_BLOCK_END" && data.text) {
        addTaskProgress({
          worker_session_id: "", worker_agent_id: agentId,
          worker_agent_name: "", reply_id: "",
          event_type: etype, event_seq: 0, timestamp: Date.now(),
          summary: data.text,
        });
        return;
      }
    },
    [addToolCallToAgent, addThinkingToAgent, updateWorkDetail, addTaskProgress],
  );

  // ── WS message handler ──────────────────────────

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

  const handleWsMessage = useCallback(
    (data: any) => {
      const type = data.type;
      const agentId = data._agent_id;

      // Handshake / heartbeat (ignore)
      if (
        type === "config:reloaded" ||
        type === "server_info" ||
        type === "session-status"
      )
        return;

      // ── Agent: busy → start SSE ──
      if (type === "agent:busy") {
        setAgentStatus(agentId || "unknown", "busy");
        if (agentId && data.session_id) {
          startSse(agentId, data.session_id);
        }
        if (agentId) {
          updateWorkDetail(agentId, { currentTask: "Working..." });
        }
        return;
      }

      // ── Agent: idle → stop SSE ──
      if (type === "agent:idle") {
        setAgentStatus(agentId || "unknown", "idle");
        if (agentId) {
          stopSse(agentId);
          updateWorkDetail(agentId, { currentTask: undefined });
        }
        return;
      }

      // ── Human message ──
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

      // ── Agent report (from report_to_group tool) ──
      if (type === "agent_report") {
        const reportAgentId = data._agent_id || "assistant";
        addMessage({
          id: `report-${reportAgentId}-${data._timestamp || Date.now()}`,
          sender: reportAgentId,
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
      if (type === "HINT_BLOCK") return;

      // ── Task progress (from projector, routed to window stream) ──
      if (type === "task_progress") {
        addTaskProgress({
          worker_session_id: data.worker_session_id || "",
          worker_agent_id: data.worker_agent_id || agentId || "unknown",
          worker_agent_name: data.worker_agent_name || "",
          reply_id: data.reply_id || "",
          event_type: data.event_type || "UnknownEvent",
          event_seq: data.event_seq || 0,
          timestamp: (data.timestamp || data._timestamp || 0) * 1000,
          delta: data.delta,
          thinking_started: data.thinking_started,
          thinking_ended: data.thinking_ended,
          tool_name: data.tool_name,
          tool_input: data.tool_input,
          tool_state: data.tool_state,
          tool_output: data.tool_output,
          tool_result_started: data.tool_result_started,
          summary: data.summary,
        });
        return;
      }

      // ── REPLY_START / REPLY_END (agent lifecycle, now via SSE) ──
      // Silently consume — SSE handles actual content.
      if (type === "REPLY_START" || type === "REPLY_END") return;

      // ── TEXT / THINKING deltas (now via SSE) ──
      if (type === "TEXT_BLOCK_DELTA" || type === "THINKING_BLOCK_DELTA") return;
      if (type === "TEXT_BLOCK_END" || type === "THINKING_BLOCK_END") return;

      // ── TOOL events (now via SSE) ──
      if (type === "TOOL_CALL_END" || type === "TOOL_RESULT_START" ||
          type === "TOOL_RESULT_END") return;
    },
    [addMessage, setAgentStatus, startSse, stopSse, updateWorkDetail, addTaskProgress],
  );

  // ── WS connection ───────────────────────────────

  const connect = useCallback(() => {
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    )
      return;

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
        handleWsMessage(JSON.parse(event.data));
      } catch (e) {
        console.warn("[WS] parse error", e);
      }
    };

    ws.onclose = () => {
      console.log("[WS] disconnected");
      setWsConnected(false);
      closeAllSse();
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
  }, [handleWsMessage, scheduleReconnect, setWsConnected, closeAllSse]);

  const sendMessage = useCallback(
    (command: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.warn("[WS] not connected, can't send");
        return;
      }
      if (!currentWindowId) return;
      const cwd =
        currentProjectPath || currentProject?.full_path || ".";

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
    closeAllSse();
    wsRef.current?.close();
    wsRef.current = null;
  }, [clearReconnectTimer, closeAllSse]);

  useEffect(() => {
    return () => {
      intentionalCloseRef.current = true;
      clearReconnectTimer();
      closeAllSse();
      wsRef.current?.close();
    };
  }, [clearReconnectTimer, closeAllSse]);

  return { connect, sendMessage, disconnect };
}
