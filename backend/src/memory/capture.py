"""
MemoryCaptureMiddleware — hybrid memory extraction from agent context.

Hangs on AgentScope 2.0.1's on_compress_context hook: when the agent's
context exceeds its token threshold and is about to be compressed, this
middleware extracts memories BEFORE the old context is discarded.

Extraction is hybrid:
  1. Rule-based — ToolCallBlock / HintBlock → direct memory entries
  2. LLM-based — TextBlock accumulation → semantic extraction (optional)

Design principles:
  - "Memory is an index, not a copy" — tool results are summarised, not stored.
  - Each agent captures its own memories independently.
  - call_* tools: only the invocation is recorded, not the result (the callee
    captures its own reply text separately).
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Callable

from agentscope.middleware import MiddlewareBase
from agentscope.message import (
    TextBlock, ToolCallBlock, ToolResultBlock, HintBlock,
    Msg,
)

from ..core.logging import get_logger

log = get_logger(__name__)

# Maximum length for rule-extracted memory content
_MAX_CONTENT_LEN = 500
_MAX_HINT_LEN = 200


class MemoryCaptureMiddleware(MiddlewareBase):
    """Extract memories from agent context on compression.

    Usage:
        middlewares = [MemoryCaptureMiddleware(agent_id="pd", project_id="my-blog",
                                                store=None, model=None)]
        Agent(..., middlewares=middlewares)
    """

    def __init__(
        self,
        *,
        agent_id: str = "",
        project_id: str = "",
    ):
        self._agent_id = agent_id
        self._project_id = project_id

    async def on_compress_context(
        self,
        agent: Any,
        input_kwargs: dict,
        next_handler: Callable[..., Any],
    ) -> None:
        """Extract memories from agent.state.context, then proceed with
        the actual compression."""
        try:
            entries = self._extract_rule_based(agent)
            if entries:
                from ..core import store as memory_store
                await memory_store.insert_memory_batch(entries)
                log.info(
                    "[memory] agent=%s captured %d entries (rule-based) | context_msgs=%d",
                    self._agent_id, len(entries), len(agent.state.context),
                )
            else:
                log.debug(
                    "[memory] agent=%s capture skipped (0 entries) | context_msgs=%d",
                    self._agent_id, len(agent.state.context),
                )
        except Exception as e:
            log.warning("[memory] agent=%s rule extraction failed: %s", self._agent_id, e)

        # Continue with the actual context compression
        await next_handler(**input_kwargs)

    # ── Rule-based extraction ──────────────────────────

    def _extract_rule_based(self, agent: Any) -> list[dict]:
        """Walk agent.state.context and extract facts/decisions from blocks."""
        entries: list[dict] = []
        for msg in agent.state.context:
            if not isinstance(msg, Msg):
                continue
            for block in msg.content:
                e = self._extract_from_block(block, msg)
                if e:
                    entries.append(e)
        return entries

    def _extract_from_block(self, block, msg) -> dict | None:
        """Extract one memory entry from a single content block."""
        if isinstance(block, ToolCallBlock):
            return self._from_tool_call(block)
        if isinstance(block, ToolResultBlock):
            return self._from_tool_result(block)
        if isinstance(block, HintBlock):
            return self._from_hint(block)
        # TextBlock / ThinkingBlock / DataBlock → left for LLM extraction
        return None

    def _from_tool_call(self, block: ToolCallBlock) -> dict | None:
        tool_name = block.name or ""
        if tool_name.startswith("call_"):
            # call_agent tool — only record invocation, not result
            target = tool_name.removeprefix("call_")
            return self._mk(
                type="decision",
                content=f"调用了 {target} 获取专业意见",
                importance=0.6,
            )
        # Regular tool invocation
        return self._mk(
            type="decision",
            content=f"调用了 {tool_name}",
            importance=0.4,
        )

    def _from_tool_result(self, block: ToolResultBlock) -> dict | None:
        # Skip results for call_agent — the callee captures its own reply
        if block.name and block.name.startswith("call_"):
            return None
        # Summarise tool result (one-line status, not full output)
        text = self._block_text_summary(block)
        if not text:
            return None
        return self._mk(
            type="fact",
            content=f"{block.name or 'Tool'} 完成: {text[:_MAX_CONTENT_LEN]}",
            importance=0.3,
        )

    def _from_hint(self, block: HintBlock) -> dict | None:
        source = block.source or "unknown"
        if isinstance(block.hint, str):
            text = block.hint
        else:
            text = " ".join(
                sub.text for sub in block.hint
                if isinstance(sub, TextBlock) and sub.text
            )
        if not text.strip():
            return None
        return self._mk(
            type="fact",
            content=f"[{source}]: {text[:_MAX_HINT_LEN]}",
            importance=0.4,
        )

    # ── Helpers ────────────────────────────────────────

    def _mk(self, type: str, content: str, importance: float = 0.5) -> dict:
        return {
            "agent_id": self._agent_id,
            "project_id": self._project_id,
            "scope": "private",
            "type": type,
            "content": content,
            "source": self._agent_id,
            "importance": importance,
        }

    @staticmethod
    def _block_text_summary(block: ToolResultBlock) -> str:
        """Extract a short summary from a ToolResultBlock's output."""
        if isinstance(block.output, str):
            return block.output
        if isinstance(block.output, list):
            parts = []
            for item in block.output:
                if isinstance(item, TextBlock):
                    parts.append(item.text)
                else:
                    parts.append(str(type(item).__name__))
            return " ".join(parts)
        return str(type(block.output).__name__)
