"""
ContextSeedingMiddleware — seed agent context from the shared window stream.

On every reply start (on_reply hook), reads recent events from the window
stream and injects them as HintBlocks into agent.state.context.

Routing rules:
  · momo: full recent N events — project-wide situational awareness
  · worker: filtered to events involving this agent — focused view

The window stream (key: ``window:{window_id}:events``) is the single source
of truth for the shared chat timeline.  TeamSay messages stay in the
per-session inbox (InboxMiddleware handles them separately).

Execution order: this middleware sits BEFORE InboxMiddleware in the chain.
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Callable

from agentscope.middleware import MiddlewareBase
from agentscope.message import AssistantMsg, HintBlock
from agentscope.event import HintBlockEvent
from agentscope.agent import Agent
from agentscope.app.message_bus import MessageBus

from .logging import get_logger

log = get_logger(__name__)

# ── Which event types are meaningful for context seeding ──
# Text deltas are too granular; REPLY_START/END carry no content.
_SEEDABLE_TYPES = {
    "TEXT_BLOCK_START", "TEXT_BLOCK_END",
    "HINT_BLOCK",
    "human_message",
}


class ContextSeedingMiddleware(MiddlewareBase):
    """Read window stream and seed agent context before reply.

    Args:
        message_bus: The application message bus (RedisMessageBus).
        window_id: The shared timeline identifier (= sessionId from frontend).
        agent_id: This agent's id, used for self-reference and filtering.
        is_momo: If True, seed ALL events (leader awareness).
        max_count: Maximum recent events to read.
    """

    def __init__(
        self,
        message_bus: MessageBus,
        window_id: str,
        agent_id: str,
        is_momo: bool = False,
        max_count: int = 30,
    ) -> None:
        self._bus = message_bus
        self._agent_id = agent_id
        self._is_momo = is_momo
        self._max_count = max_count
        # Extract bare window_id from session format "web_s_xxx:momo"
        self._window_id = window_id.rsplit(":", 1)[0] if ":" in window_id else window_id
        self._window_key = f"window:{self._window_id}:events"

    # ── AgentScope on_reply hook ───────────────────────

    async def on_reply(
        self,
        agent: Agent,
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator[Any, None]:
        """Seed context from window stream, then continue the reply chain.

        Only seeds when agent.state.context is empty or only has
        onboarding messages — avoids double-seeding on retriggers.
        """
        # ── Read window stream ──────────────────────
        # momo: read max_count events (full situational awareness).
        # worker: read up to max_count * 3, filter to find self-relevant
        # events, and keep interleaving context between them.
        read_count = self._max_count
        if not self._is_momo:
            read_count = min(self._max_count * 3, 200)

        try:
            entries = await self._bus.log_read(
                self._window_key, max_count=read_count,
            )
        except Exception:
            log.debug(
                "ContextSeeding: cannot read window stream %s (new window?)",
                self._window_key[:40],
            )
            entries = []

        # ── For worker: filter to relevant + interleaving context ──
        if not self._is_momo and entries:
            entries = _truncate_for_worker(entries, self._agent_id, self._max_count)

        # ── Filter + format ─────────────────────────
        hints: list[HintBlock] = []
        for _entry_id, payload in entries:
            if not self._involves_me(payload):
                continue
            hint_text = self._format(payload)
            if hint_text:
                hints.append(HintBlock(
                    hint=hint_text,
                    source=payload.get("_agent_id", payload.get("speaker_id", "")),
                ))

        if hints:
            # ── Inject into agent context ──────────
            if agent.state.context:
                last_msg = agent.state.context[-1]
                if last_msg.role == "assistant" and last_msg.name == agent.name:
                    last_msg.content.extend(hints)
                else:
                    agent.state.context.append(
                        AssistantMsg(
                            id=agent.state.reply_id,
                            name=agent.name,
                            content=list(hints),
                        ),
                    )
            else:
                agent.state.context.append(
                    AssistantMsg(
                        id=agent.state.reply_id,
                        name=agent.name,
                        content=list(hints),
                    ),
                )

            # Yield one-shot events for the front-end SSE/WS stream
            for hint in hints:
                yield HintBlockEvent(
                    reply_id=agent.state.reply_id,
                    block_id=hint.id,
                    source=hint.source,
                    hint=hint.hint,
                )

            log.info(
                "ContextSeeding: %d hints seeded for agent=%s window=%s momo=%s",
                len(hints),
                self._agent_id,
                self._window_id[:20],
                self._is_momo,
            )
        else:
            log.debug(
                "ContextSeeding: no matching events for agent=%s window=%s",
                self._agent_id,
                self._window_id[:20],
            )

        # ── Continue the middleware chain ───────────
        async for event in next_handler(**input_kwargs):
            yield event

    # ── Helpers ────────────────────────────────────

    def _involves_me(self, event: dict) -> bool:
        """Check if this window event involves the current agent.

        momo sees everything (full situational awareness).
        Workers only see events that mention their agent_id or are human messages.
        """
        if self._is_momo:
            return True

        # Human messages: always relevant (could be addressed to anyone)
        if event.get("type") == "human_message":
            return True

        # Quick string search for agent_id in the full payload
        payload_str = json.dumps(event, ensure_ascii=False)
        return self._agent_id in payload_str

    @staticmethod
    def _format(event: dict) -> str:
        """Convert a window stream event into a one-line context hint.

        Text deltas are skipped (too granular); text block starts/ends
        carry the full text accumulated by WindowPublishMiddleware.
        """
        t = event.get("type", "")

        if t == "human_message":
            speaker = event.get("speaker_id", "user")
            content = event.get("content", "")
            return f"👤 {speaker}: {content[:200]}"

        if t in ("HINT_BLOCK", "hint"):
            return event.get("hint", event.get("content", ""))[:200]

        if t == "TEXT_BLOCK_END":
            agent_id = event.get("_agent_id", "")
            text = event.get("text", event.get("content", ""))
            if text:
                return f"🤖 {agent_id}: {text[:200]}"

        if t == "TOOL_CALL_END":
            agent_id = event.get("_agent_id", "")
            tool_name = event.get("tool_name", event.get("name", "?"))
            return f"🔧 {agent_id} 调用 {tool_name}"

        if t == "TOOL_RESULT_END":
            agent_id = event.get("_agent_id", "")
            state = event.get("state", "")
            return f"✅ {agent_id} 工具{'完成' if state == 'success' else '失败'}"

        return ""


# ── Worker context truncation ──────────────────────


def _is_relevant(event: dict, agent_id: str) -> bool:
    """Return True if this event involves the given agent.

    The event is relevant if: it's a human_message, or the agent_id
    appears anywhere in the serialized payload.
    """
    t = event.get("type", "")
    if t == "human_message":
        return True
    payload_str = json.dumps(event, ensure_ascii=False)
    return agent_id in payload_str


def _truncate_for_worker(
    entries: list,
    agent_id: str,
    max_total: int,
) -> list:
    """Keep entries that are relevant to this worker, plus interleaving
    context between them.  Read from the end (most recent), keep at most
    max_total entries total.

    Strategy:
      1. Walk entries from end to start.
      2. Track the gap since the last relevant entry.
      3. Keep relevant entries + up to 2 interleaving entries between them.
      4. Stop when we've kept max_total entries total.
    """
    if not entries:
        return entries

    kept: list = []
    gap: list = []
    max_gap = 2  # keep at most 2 interleaving messages between relevant ones

    for _entry_id, payload in reversed(entries):
        if _is_relevant(payload, agent_id):
            # Flush gap (keep at most max_gap interleaving)
            kept.extend(reversed(gap[-max_gap:]))
            gap = []
            kept.append((_entry_id, payload))
        else:
            gap.append((_entry_id, payload))

    # Reverse back to chronological order
    kept.reverse()
    # Cap at max_total
    return kept[-max_total:]

