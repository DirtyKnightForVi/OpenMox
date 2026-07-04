"""
AgentStatusProjector — publishes agent:busy / agent:idle to the window
stream when worker sessions are invoked via WakeupDispatcher (TeamSay).

The WakeupDispatcher calls ``ChatService.run()`` directly, bypassing
``_run_one`` in chat.py.  Without this projector, the frontend never
knows a worker has started — no SSE connection, no task panel updates.

Hooks into agentscope's EventProjector: fires on ReplyStartEvent
(→ agent:busy) and ReplyEndEvent (→ agent:idle) for sessions that
participate in a team as workers.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from agentscope.event import ReplyStartEvent, ReplyEndEvent

if TYPE_CHECKING:
    from agentscope.app.storage import AgentRecord, SessionRecord, StorageBase
    from agentscope.app.message_bus import MessageBus
    from agentscope.event import AgentEvent
    from agentscope.app._service._session_projection import SessionProjection


class AgentStatusProjector:
    """Publish agent:busy / agent:idle to the window stream for workers.

    Only acts on worker sessions (team participants that are NOT the
    leader). The leader's busy/idle is already handled by _run_one.
    """

    def __init__(self, message_bus: "MessageBus") -> None:
        self._bus = message_bus

    async def maybe_project(
        self,
        user_id: str,
        session_record: "SessionRecord",
        agent_record: "AgentRecord",
        event: "AgentEvent",
        projection: "SessionProjection",
    ) -> None:
        """Fire on reply start/end for worker sessions."""
        # Only care about reply lifecycle events
        if not isinstance(event, (ReplyStartEvent, ReplyEndEvent)):
            return

        # Only sessions in a team
        if not session_record.team_id:
            return

        # Extract window_id from session_id: "{window_id}:{agent_id}"
        window_id = (
            session_record.id.rsplit(":", 1)[0]
            if ":" in session_record.id
            else session_record.id
        )

        if isinstance(event, ReplyStartEvent):
            payload = {
                "type": "agent:busy",
                "_agent_id": agent_record.id,
                "session_id": session_record.id,
                "_timestamp": time.time(),
            }
        else:
            payload = {
                "type": "agent:idle",
                "_agent_id": agent_record.id,
                "_timestamp": time.time(),
            }

        window_key = f"window:{window_id}:events"
        try:
            await self._bus.log_append(window_key, payload, max_len=2000)
            await self._bus.publish(window_key, payload)
        except Exception:
            pass
