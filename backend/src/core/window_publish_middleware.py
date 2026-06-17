"""
WindowPublishMiddleware — selectively publish agent events to the shared window stream.

This middleware runs as the LAST middleware in the chain (after all other hooks).
It intercepts events produced by agent.reply_stream() and publishes a filtered
subset to the window-level stream (key: ``window:{window_id}:events``).

Filtering rules:
  · IN:  TEXT_BLOCK_START/END (final reply text), TOOL_CALL_END, TOOL_RESULT_END,
         HINT_BLOCK (injected context), REPLY_START/END, EXCEED_MAX_ITERS
  · OUT: THINKING_BLOCK_* (internal reasoning), MODEL_CALL_* (LLM metadata),
         TEXT_BLOCK_DELTA (too granular — final text captured by _END)

The window stream is consumed by:
  · Frontend WebSocket — renders the shared chat timeline
  · ContextSeedingMiddleware — seeds agent context from the shared history
"""

from __future__ import annotations

import time
from typing import Any, AsyncGenerator, Callable

from agentscope.middleware import MiddlewareBase
from agentscope.agent import Agent
from agentscope.app.message_bus import MessageBus

from .logging import get_logger

log = get_logger(__name__)

# ── Events published to the window stream ────────────

_PUBLIC_EVENT_TYPES: set[str] = {
    "REPLY_START",
    "REPLY_END",
    "TEXT_BLOCK_START",
    "TEXT_BLOCK_END",
    "TOOL_CALL_END",
    "TOOL_RESULT_START",
    "TOOL_RESULT_END",
    "HINT_BLOCK",
    "EXCEED_MAX_ITERS",
    "THINKING_BLOCK_START",
    "THINKING_BLOCK_END",
}

# ── Max events retained in the window stream ─────────

_WINDOW_STREAM_MAX_LEN = 2000


class WindowPublishMiddleware(MiddlewareBase):
    """Publish selected agent events to the window-level shared stream.

    Every agent run writes to the same window stream, creating a shared
    timeline that all participants (human included) can read from.

    Args:
        message_bus: The application message bus (RedisMessageBus).
        window_id: The shared timeline identifier (= sessionId from frontend).
        agent_id: This agent's id, tagged on every published event as _agent_id.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        window_id: str,
        agent_id: str,
    ) -> None:
        self._bus = message_bus
        self._agent_id = agent_id
        # window_id may be "web_s_xxx:momo" (session format).
        # Extract the bare window_id so all agents in the same window
        # write to the same window stream key.
        self._window_id = window_id.rsplit(":", 1)[0] if ":" in window_id else window_id
        self._window_key = f"window:{self._window_id}:events"

    # ── AgentScope on_reply hook (wraps the whole reply) ──

    async def on_reply(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator[Any, None]:
        """Wrap the entire reply, filtering + publishing public events."""
        text_buffer: str = ""
        _event_idx = 0

        async for event in next_handler(**input_kwargs):
            _event_idx += 1
            event_type = getattr(event, "type", None) or event.__class__.__name__

            # ── Accumulate text deltas ─────────────
            if event_type == "TEXT_BLOCK_DELTA":
                delta = getattr(event, "delta", "")
                text_buffer += delta
                yield event
                continue

            # ── Flush accumulated text on block end ──
            if event_type == "TEXT_BLOCK_END" and text_buffer:
                await self._publish({
                    "type": "TEXT_BLOCK_END",
                    "_agent_id": self._agent_id,
                    "_timestamp": time.time(),
                    "text": text_buffer,
                })
                text_buffer = ""
                yield event
                continue

            # ── Publish other public events ─────────
            if event_type in _PUBLIC_EVENT_TYPES:
                try:
                    payload = event.model_dump(mode="json", exclude_none=True)
                except Exception:
                    payload = {"type": event_type}

                payload["_agent_id"] = self._agent_id
                payload["_timestamp"] = time.time()
                # Log tool calls with name for debugging
                if event_type in ("TOOL_CALL_END", "TOOL_RESULT_END"):
                    tool_name = payload.get("name", "?")
                    tool_state = payload.get("state", "")
                    log.debug(
                        "WindowPublish: agent=%s %s tool=%s state=%s",
                        self._agent_id, event_type, tool_name, tool_state,
                    )
                await self._publish(payload)

            yield event

        # ── End of reply: flush any remaining text ──
        if text_buffer:
            await self._publish({
                "type": "TEXT_BLOCK_END",
                "_agent_id": self._agent_id,
                "_timestamp": time.time(),
                "text": text_buffer,
            })

        log.info("WindowPublish: agent=%s reply finished, %d events, text=%d chars",
                 self._agent_id, _event_idx, len(text_buffer))

    async def _publish(self, payload: dict) -> None:
        """Write one event to the window stream (replay log + live pub/sub)."""
        try:
            await self._bus.log_append(
                self._window_key,
                payload,
                max_len=_WINDOW_STREAM_MAX_LEN,
            )
            await self._bus.publish(self._window_key, payload)
            # Debug: log every published event for troubleshooting
            log.debug(
                "WindowPublish: agent=%s type=%s key=%s",
                self._agent_id,
                payload.get("type", "?"),
                self._window_key[:30],
            )
        except Exception:
            pass  # best-effort; don't break the reply chain
