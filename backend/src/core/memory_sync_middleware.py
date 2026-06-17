"""
MemorySyncMiddleware — detect agent writes to MEMORY.md / PROJECT_MEMO.md
and sync the content back to SQLite memory_entries.

Hooks into AgentScope's on_acting middleware hook.  After every tool
call that writes to a memory file, parses the file content and upserts
entries to the database.

Registered after CommunicationBudgetMiddleware and before
WindowPublishMiddleware in the middleware chain.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Callable, TYPE_CHECKING

from agentscope.middleware import MiddlewareBase
from agentscope.tool import ToolChunk

from .logging import get_logger

if TYPE_CHECKING:
    from agentscope.agent import Agent

log = get_logger(__name__)

# Paths that trigger memory sync on write
_MEMORY_PATHS = (".Agents/", "MEMORY.md", ".Project/PROJECT_MEMO.md")


class MemorySyncMiddleware(MiddlewareBase):
    """After a Write/Edit to MEMORY.md, sync content back to SQLite.

    This is the "local → cloud" direction of the bidirectional memory
    bridge.  The reverse direction (cloud → local) is handled by the
    REST sync API or Dream engine.
    """

    def __init__(
        self,
        agent_id: str = "",
        project_root: str = ".",
    ) -> None:
        self._agent_id = agent_id
        self._project_root = project_root

    # ── AgentScope on_acting hook ──────────────────────

    async def on_acting(
        self,
        agent: "Agent",
        input_kwargs: dict,
        next_handler: Callable[..., AsyncGenerator],
    ) -> AsyncGenerator["ToolChunk | ToolResponse", None]:
        """Wrap tool execution, detect memory file writes, sync back."""
        tool_call = input_kwargs.get("tool_call")
        tool_name = getattr(tool_call, "name", "") if tool_call else ""
        raw_input = getattr(tool_call, "input", {}) or {}
        # tool_call.input can be a JSON string from the model
        if isinstance(raw_input, str):
            import json
            try:
                tool_input: dict[str, Any] = json.loads(raw_input)
            except (json.JSONDecodeError, TypeError):
                tool_input = {}
        else:
            tool_input = raw_input

        # Check if this tool call targets a memory file
        file_path = tool_input.get("file_path", "")
        should_sync = (
            tool_name in ("Write", "Edit")
            and any(pat in file_path for pat in _MEMORY_PATHS)
        )

        # Execute the tool normally
        async for event in next_handler(tool_call=tool_call):
            yield event

        # After execution, sync if applicable
        if should_sync:
            try:
                from ..memory.sync import sync_markdown_to_entries
                scope = "shared" if "PROJECT_MEMO" in file_path else "private"
                count = await sync_markdown_to_entries(
                    agent_id=self._agent_id,
                    project_root=self._project_root,
                    scope=scope,
                )
                if count > 0:
                    log.info(
                        "[memory sync] %s wrote %s → SQLite (%d entries)",
                        self._agent_id, file_path[-40:], count,
                    )
            except Exception as e:
                log.warning(
                    "[memory sync] failed to sync %s: %s",
                    file_path[-40:], e,
                )
