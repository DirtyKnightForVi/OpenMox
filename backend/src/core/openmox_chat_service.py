"""
OpenMoxChatService — ChatService subclass that filters out AgentScope
built-in tools that conflict with our design:

Removed from leader toolkit:
  - AgentCreate   — creates ephemeral Redis workers; our design uses
                    YAML templates + SubAgentTemplate mapping
  - AgentInvite   — invites existing agents to teams; our design manages
                    team membership via .Project/team.yaml
  - TeamCreate    — AgentScope's team management; our design manages
                    teams per-project via .Project/team.yaml
  - TaskCreate / TaskList / TaskGet / TaskUpdate
                  — AgentScope's built-in planning tools that don't
                    know about DASHBOARD.yaml; our equivalents are
                    create_task_plan / update_dashboard

Kept:
  - TeamSay       — inter-agent communication (core to our design)
  - TeamDelete    — safe to keep (won't be used without TeamCreate)
  - Schedule*     — retained; agentscope cron scheduling (non-conflicting)
  - ToolStop      — retained; offloaded tool cancellation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentscope.app._service._chat import ChatService
from agentscope.app._service._toolkit import get_toolkit

if TYPE_CHECKING:
    from agentscope.app.storage import StorageBase
    from agentscope.app.message_bus import MessageBus
    from agentscope.app._types import (
        AgentToolFactory,
        AgentMiddlewareFactory,
        EventProjector,
        SubAgentTemplate,
    )
    from agentscope.app._manager import (
        SchedulerManager,
        BackgroundTaskManager,
        ChatRunRegistry,
    )
    from agentscope.app.workspace_manager import WorkspaceManagerBase


# Tools that AgentScope injects automatically but we DON'T want.
# These conflict with our YAML-based agent management and dashboard system.
_UNWANTED_TOOLS: set[str] = {
    "AgentCreate",      # ephemeral Redis worker → use YAML templates
    "AgentInvite",      # invite agents to team → use .Project/team.yaml
    "TeamCreate",       # AgentScope team → use .Project/team.yaml
    # TaskCreate/TaskList/TaskGet/TaskUpdate are KEPT — workers use them
    # for the plan-execute loop (TaskContext auto-injected by _run_one).
}


class OpenMoxChatService(ChatService):
    """ChatService that filters out unwanted AgentScope built-in tools."""

    def __init__(
        self,
        *,
        storage: "StorageBase",
        workspace_manager: "WorkspaceManagerBase",
        scheduler_manager: "SchedulerManager",
        background_task_manager: "BackgroundTaskManager",
        message_bus: "MessageBus",
        extra_agent_tools: "AgentToolFactory | None" = None,
        extra_agent_middlewares: "AgentMiddlewareFactory | None" = None,
        extra_projectors: "list[EventProjector] | None" = None,
        custom_subagent_templates: "dict[str, SubAgentTemplate] | None" = None,
    ) -> None:
        super().__init__(
            storage=storage,
            workspace_manager=workspace_manager,
            scheduler_manager=scheduler_manager,
            background_task_manager=background_task_manager,
            message_bus=message_bus,
            extra_agent_tools=extra_agent_tools,
            extra_agent_middlewares=extra_agent_middlewares,
            extra_projectors=extra_projectors,
            custom_subagent_templates=custom_subagent_templates,
        )

    async def _run_impl(
        self,
        user_id: str,
        session_id: str,
        agent_id: str,
        input_msg,
    ) -> None:
        """Override: filter toolkit after assembly, then delegate to parent.

        The parent's _run_impl calls get_toolkit() internally.  We can't
        intercept that call without copying the entire ~250-line method.
        Instead, we monkey-patch get_toolkit for the duration of this call
        so the returned toolkit has unwanted tools stripped.
        """
        import agentscope.app._service._chat as _chat_module

        _original = _chat_module.get_toolkit

        async def _filtered_get_toolkit(**kwargs):
            toolkit = await _original(**kwargs)
            # Filter unwanted tools from each tool group
            for group in toolkit.tool_groups:
                group.tools = [
                    t for t in (group.tools or [])
                    if t.name not in _UNWANTED_TOOLS
                ]
            return toolkit

        _chat_module.get_toolkit = _filtered_get_toolkit
        try:
            await super()._run_impl(user_id, session_id, agent_id, input_msg)
        finally:
            _chat_module.get_toolkit = _original
