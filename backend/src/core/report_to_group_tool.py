"""
ReportToGroup — agent sends a complete, deliberate message to the group chat.

Unlike the old streaming model (where TEXT_BLOCK_DELTA events were
published to the window stream and the frontend stitched them together),
ReportToGroup publishes a single, complete Markdown message. This eliminates
race conditions (lost deltas, stuck "thinking..." animations) and aligns
with how real group chats work: you compose your message, then hit send.

The agent's system prompt must instruct it to use this tool when it wants
to communicate with the human or momo in the group chat — not to rely on
text output (which stays private to the task panel via SSE).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior

from .openmox_tool_base import OpenMoxToolBase

if TYPE_CHECKING:
    from agentscope.app.storage import StorageBase
    from agentscope.app.message_bus import MessageBus


class ReportToGroup(OpenMoxToolBase):
    """Send a complete message to the group chat window.

    This is the ONLY way an agent should communicate with humans or momo
    in the group chat. Internal thinking, tool calls, and intermediate
    text are visible in the task panel (via SSE) but do NOT appear in
    the group chat window.
    """

    name: str = "report_to_group"
    description: str = (
        "向群聊窗口发送一条完整的汇报消息。"
        "只有通过这个工具发送的消息才会出现在群聊中。"
        "你的内部思考、工具调用、中间结果都不会进群聊——它们只在任务面板中可见。"
        "参数: content(必填, Markdown格式的完整消息内容)。"
        "使用时机: 当你完成一个任务阶段、需要向人类汇报进展、"
        "或者需要向momo请求帮助时。"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": (
                    "要发送到群聊的完整消息（Markdown 格式）。"
                    "消息应该完整、自成一体，包含你的结论、数据或请求。"
                    "可以使用 Markdown 表格、列表、代码块等格式。"
                ),
            },
        },
        "required": ["content"],
    }
    is_concurrency_safe: bool = True
    is_read_only: bool = False

    async def __call__(self, content: str) -> str:
        """Publish the message to the window stream and persist to SQLite.

        Returns a brief confirmation so the agent knows the message was sent.
        """
        if not content.strip():
            return "[错误] 消息内容不能为空"

        # Extract window_id from session_id: "{window_id}:{agent_id}"
        window_id = (
            self._window_id.rsplit(":", 1)[0]
            if ":" in self._window_id
            else self._window_id
        )
        window_key = f"window:{window_id}:events"

        # Build the event payload
        payload = {
            "type": "agent_report",
            "content": content,
            "_agent_id": self._agent_id,
            "_timestamp": time.time(),
        }

        # Publish to window stream (replay log + live Pub/Sub)
        try:
            await self._message_bus.log_append(window_key, payload, max_len=2000)
            await self._message_bus.publish(window_key, payload)
        except Exception as e:
            return f"[错误] 发送消息到群聊失败: {e}"

        # Persist to SQLite messages table for history
        try:
            from ..core.store import append_message
            await append_message(
                window_id,
                content=content,
                speaker_type="agent",
                speaker_id=self._agent_id,
            )
        except Exception:
            pass  # best-effort persistence

        preview = content[:80].replace("\n", " ")
        return f"✓ 已发送到群聊: {preview}..."
