"""
OpenMoxToolBase — unified tool base class for all OpenMox tools.

Inherits AgentScope 2.0.1's _TeamToolBase so that every OpenMox tool
receives the standard (storage, message_bus, user_id, session_id, agent_id)
injection.  From storage we extract our own DAO layer (ConfigDAO /
DashboardDAO) so that existing tool subclasses continue to work with
self._dao / self._dashboard_dao.

This fixes the 09-plan gap: our tools now flow through the same dependency
stack as AgentScope's TeamSay / AgentCreate / TeamDelete.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agentscope.app._tools._team_tool_base import _TeamToolBase
from agentscope.tool import ToolBase
from agentscope.permission import PermissionContext, PermissionDecision, PermissionBehavior

if TYPE_CHECKING:
    from ..dao.config_dao import ConfigDAO
    from ..dao.dashboard_dao import DashboardDAO
    from agentscope.app.storage import StorageBase
    from agentscope.app.message_bus import MessageBus


class OpenMoxToolBase(_TeamToolBase):
    """Base class for all OpenMox tools with unified dependency injection.

    Constructor accepts AgentScope's standard five:
      - storage: StorageBase instance (e.g. OpenMoxRedisStorage, connects to ConfigDAO + DashboardDAO)
      - message_bus: MessageBus instance (e.g. RedisMessageBus)
      - user_id: always "openmox" (single-user mode)
      - session_id: = window_id (current conversation window)
      - agent_id: the agent that owns this tool instance

    The base class automatically extracts self._dao, self._dashboard_dao,
    self._window_id, self._agent_id, and self._is_momo from these five
    standard parameters, so that all existing OpenMox tool subclasses
    (UpdateDashboardTool, CreateTaskPlanTool, WriteSharedMemoryTool,
    AgentFromTemplateTool) continue to reference them without changes.
    """

    # ── Convenience aliases (set by __init__) ─────────

    _dao: Any
    """ConfigDAO — agent YAML, templates, onboarding context."""

    _dashboard_dao: Any
    """DashboardDAO — task DAG read/write."""

    _window_id: str
    """Current conversation window id (empty = not in a window)."""

    _is_momo: bool
    """Whether the calling agent is the project's momo."""

    def __init__(
        self,
        *,
        storage: "StorageBase",
        message_bus: "MessageBus",
        user_id: str = "openmox",
        session_id: str = "",
        agent_id: str = "",
        is_momo: bool | None = None,
    ) -> None:
        """Hand off to _TeamToolBase first, then extract our DAOs.

        Args:
            storage: StorageBase (provides ._dao and ._dashboard_dao via OpenMoxRedisStorage).
            message_bus: MessageBus (RedisMessageBus for Agent Team communication).
            user_id: Always "openmox" in single-user mode.
            session_id: Window id for the current conversation.
            agent_id: The agent that owns this tool.
            is_momo: Override for tests where the agent may not exist
                     in the YAML config.  If None, derived from _dao.is_momo().
        """
        super().__init__(
            storage=storage,
            message_bus=message_bus,
            user_id=user_id,
            session_id=session_id,
            agent_id=agent_id,
        )
        # Extract OpenMox-specific DAOs from the storage adapter.
        # Tools reference these directly (self._dao / self._dashboard_dao).
        self._dao = getattr(storage, "_dao", None)
        self._dashboard_dao = getattr(storage, "_dashboard_dao", None)
        self._window_id = session_id
        if is_momo is not None:
            self._is_momo = is_momo
        elif self._dao is not None:
            self._is_momo = self._dao.is_momo(agent_id)
        else:
            self._is_momo = False

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """Default: always ALLOW. Override in subclasses for tool-level gating."""
        return PermissionDecision(
            behavior=PermissionBehavior.ALLOW,
            message=f"{self.name} — gating is at registration or __call__ time",
        )
