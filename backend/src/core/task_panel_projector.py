"""
TaskPanelProjector — projects worker's internal task-execution events
onto the leader (momo) session so the front-end task panel can render
a collapsible, real-time work-progress feed.

Uses agentscope 2.0.4dev's ``EventProjector`` protocol + ``SessionProjection``
primitive — zero new storage, zero new Pub/Sub channels. Every projected
event lands in the leader session's Redis projection hash and a live
``CustomEvent(name="task_progress")`` is published to the leader's event
stream so the front-end can update in real time.

Architecture (reuses agentscope's built-in cross-session mirroring):

    Worker Session (dev-manager, executing task-abc)
      │
      ├── ThinkingBlockDelta  ──→ TaskPanelProjector.maybe_project()
      ├── ToolCallEnd         ──→   ├── projection.upsert(leader_sid, ...)
      ├── ToolResultEnd       ──→   └── projection.publish(leader_sid, ...)
      └── TextBlockEnd        ──→
                                      ↓
    Leader Session (momo)             ↓
      └── Redis hash: projection:{leader_sid}
            └── task_panel:{worker_sid}:{reply_id}:{seq} → payload
      └── Event stream: CustomEvent(name="task_progress", value=payload)

Front-end subscribes to leader session SSE → filters CustomEvent(name="task_progress")
→ groups by worker → renders collapsible task panel cards.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from agentscope.event import (
    ThinkingBlockStartEvent,
    ThinkingBlockDeltaEvent,
    ThinkingBlockEndEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
    ToolResultStartEvent,
    ToolResultEndEvent,
    TextBlockEndEvent,
)

if TYPE_CHECKING:
    from agentscope.app.storage import AgentRecord, SessionRecord, StorageBase
    from agentscope.event import AgentEvent
    from agentscope.app._service._session_projection import SessionProjection


class TaskPanelProjector:
    """Project worker's internal events to the leader's task-panel feed.

    Implements the :class:`~agentscope.app._types.EventProjector` protocol
    (duck-typed — just needs ``maybe_project``).

    Only projects events from **worker** sessions (those in a team where
    this session is NOT the leader). The leader's own events stay on its
    own stream (visible in group chat); only worker-internal events that
    would otherwise be invisible to the leader are projected.
    """

    KIND = "task_panel"
    """Projection feed key — namespaces entries within a session's shared
    projection hash so the task panel feed coexists with other feeds
    (e.g. ``subagent_hitl``)."""

    EVT_PROGRESS = "task_progress"
    """``CustomEvent.name`` used to push live task-progress updates to the
    leader's event stream."""

    # Events we project to the task panel.
    _PROJECTED_EVENT_TYPES = (
        ThinkingBlockStartEvent,
        ThinkingBlockDeltaEvent,
        ThinkingBlockEndEvent,
        ToolCallStartEvent,
        ToolCallEndEvent,
        ToolResultStartEvent,
        ToolResultEndEvent,
        TextBlockEndEvent,
    )

    def __init__(
        self,
        storage: "StorageBase",
    ) -> None:
        """Bind storage for team/leader resolution.

        Args:
            storage: Application storage, used to resolve the team
                     (and hence the leader session) a worker belongs to.
        """
        self._storage = storage
        self._seq: dict[str, int] = {}
        """Per-(session_id, reply_id) sequence counter for stable entry ids."""

    # ── EventProjector protocol ──────────────────────

    async def maybe_project(
        self,
        user_id: str,
        session_record: "SessionRecord",
        agent_record: "AgentRecord",
        event: "AgentEvent",
        projection: "SessionProjection",
    ) -> None:
        """Project a worker's internal event to the leader's task-panel feed.

        Fast-path exits:
        - Session is not in a team → nothing to project.
        - Event type is not one we care about → skip.
        - Session IS the leader → skip (leader's own events visible natively).

        Args:
            user_id: The owner of the running session.
            session_record: The currently-running session's record.
            agent_record: The currently-running agent's record.
            event: The event just produced by the agent.
            projection: Shared ``SessionProjection`` primitive.
        """
        # Fast path 1: only team-participating sessions project
        if not session_record.team_id:
            return

        # Fast path 2: only project our tracked event types
        if not isinstance(event, self._PROJECTED_EVENT_TYPES):
            return

        # Resolve leader via storage (injected at construction time,
        # same pattern as SubagentHitlProjector).
        team = await self._storage.get_team(user_id, session_record.team_id)
        if team is None:
            return
        if team.session_id == session_record.id:
            # This IS the leader — nothing to project.
            return

        leader_sid = team.session_id

        # Build the event payload.
        event_type = type(event).__name__
        reply_id = getattr(event, "reply_id", "")
        seq_key = f"{session_record.id}:{reply_id}"
        seq = self._seq.get(seq_key, 0)
        self._seq[seq_key] = seq + 1

        payload = {
            "worker_session_id": session_record.id,
            "worker_agent_id": agent_record.id,
            "worker_agent_name": agent_record.data.name,
            "reply_id": reply_id,
            "event_type": event_type,
            "event_seq": seq,
            "timestamp": time.time(),
        }

        # Extract event-specific content.
        if isinstance(event, ThinkingBlockDeltaEvent):
            payload["delta"] = event.delta
        elif isinstance(event, ThinkingBlockStartEvent):
            payload["thinking_started"] = True
        elif isinstance(event, ThinkingBlockEndEvent):
            payload["thinking_ended"] = True
        elif isinstance(event, ToolCallStartEvent):
            payload["tool_name"] = event.tool_call_name
        elif isinstance(event, ToolCallEndEvent):
            # ToolCallEndEvent has no 'name' — tool name comes from
            # ToolCallStartEvent which always fires first.
            pass
        elif isinstance(event, ToolResultEndEvent):
            payload["tool_state"] = getattr(event, "state", "")
            payload["tool_output"] = getattr(event, "output", "")
        elif isinstance(event, ToolResultStartEvent):
            payload["tool_result_started"] = True
        elif isinstance(event, TextBlockEndEvent):
            text = getattr(event, "text", "")
            if text:
                payload["summary"] = text[:500]  # cap to avoid huge payloads

        # Persist to leader's projection hash (durable).
        entry_id = f"{session_record.id}:{reply_id}:{seq:04d}"
        await projection.upsert(leader_sid, self.KIND, entry_id, payload)

        # Publish to leader's session stream (session-projection native).
        # Frontend receives via SSE connection to leader's session.
        await projection.publish(leader_sid, self.EVT_PROGRESS, payload)

        from .logging import get_logger
        _log = get_logger(__name__)
        _log.info(
            "TaskPanel: projecting %s seq=%d worker=%s → leader=%s",
            event_type, seq, agent_record.id, leader_sid[:20],
        )
